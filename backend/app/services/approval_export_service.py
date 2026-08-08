"""审批中心异步导出：复用统一 ExportJob + scheduler + 文件对象 + 一次性下载票据。"""
from __future__ import annotations

import json
import socket
import uuid
from datetime import datetime, timedelta
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import and_, or_, select

from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
from app.core.exceptions import AppException, no_permission
from app.core.permissions import has_permission
from app.db.session import db_enabled, get_sessionmaker
from app.models.data_exchange import ExportJob
from app.services.data_exchange_job_service import _export_row, _write_generated_file
from app.services.db_service import _tid
from app.services.message_identity import resolve_message_user_id

MODULE_CODE = "APPROVAL"
EXPORT_TYPE = "APPROVAL_CENTER_XLSX"
ADAPTER_TYPE = "APPROVAL_CENTER"
_ALLOWED_SCOPES = {"TODO", "DONE", "RETURNED", "CC", "TEMPLATE"}
_MAX_ATTEMPTS = 5
_LEASE_SECONDS = 10 * 60
_PAGE_SIZE = 500
_TTL_HOURS = 24
_WORKER_ID = f"{socket.gethostname()}:{uuid.uuid4().hex[:12]}"

_COLUMNS = (
    ("id", "任务/模板ID"),
    ("title", "标题/名称"),
    ("bizType", "业务类型"),
    ("status", "状态"),
    ("actedAt", "办理时间"),
    ("reason", "原因/说明"),
)


def _now() -> datetime:
    return datetime.utcnow()


def _user(user=None) -> dict:
    return dict(user or get_current_user_ctx() or {})


def _require_db() -> None:
    if not db_enabled():
        raise AppException(
            "APPROVAL_BACKEND_UNAVAILABLE",
            "审批导出需要真实数据库，当前不可产生假成功",
            http_status=503,
        )


def _require_manage(user=None) -> None:
    actor = _user(user)
    if not (has_permission(actor, "*") or has_permission(actor, "approval.manage")):
        raise no_permission("无审批中心管理权限（approval.manage）")


def _actor_id(user: dict) -> int | None:
    return resolve_message_user_id(user or {}) or None


def _safe_user_snapshot(user: dict) -> dict:
    allowed = {
        "userId", "sub", "loginName", "realName", "userType", "currentRoleCode",
        "activeContextId", "permissions", "permissionCodes", "roles", "roleCodes",
        "dataScope", "dataScopes", "scopeType", "scopeIds", "tenantId",
    }
    snapshot: dict = {}
    for key in allowed:
        value = (user or {}).get(key)
        if value is None:
            continue
        try:
            json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            continue
        snapshot[key] = value
    return snapshot


def _normalize(scope, purpose) -> tuple[str, str]:
    scope = str(scope or "").strip().upper()
    if scope not in _ALLOWED_SCOPES:
        raise AppException("VALIDATION_ERROR", "未知审批导出范围", http_status=400)
    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填且不少于 5 字", http_status=400)
    return scope, purpose


def _load_page(scope: str, page: int, page_size: int, *, user: dict):
    from app.services import approval_returned_service as returned_service
    from app.services import approval_runtime_service as runtime
    from app.services import approval_template_service as template_service

    if scope == "TODO":
        return runtime.list_tasks(page, page_size, user=user)
    if scope == "DONE":
        return runtime.list_processed(page, page_size, user=user)
    if scope == "RETURNED":
        return returned_service.list_returned(page, page_size, user=user)
    if scope == "CC":
        return runtime.list_cc(page, page_size, user=user)
    return template_service.list_templates(page, page_size, user=user)


def _cell(row: dict, key: str):
    if key == "id":
        return str(row.get("taskId") or row.get("id") or "")
    if key == "title":
        return str(row.get("title") or row.get("name") or "")
    if key == "bizType":
        return str(row.get("sourceBizType") or row.get("bizType") or "")
    if key == "status":
        return str(row.get("rectifyStatus") or row.get("status") or "")
    if key == "actedAt":
        return str(row.get("actedAt") or row.get("updatedAt") or row.get("ccTime") or "")
    if key == "reason":
        return str(row.get("actionReason") or row.get("reason") or row.get("ccReason") or "")
    return ""


def create_job(scope, purpose, *, user=None) -> dict:
    """Web 请求只冻结范围和数据权限并创建任务，不生成 XLSX。"""
    _require_db()
    _require_manage(user)
    scope, purpose = _normalize(scope, purpose)
    actor = _user(user)
    _sample, total = _load_page(scope, 1, 1, user=actor)
    actor_id = _actor_id(actor)
    now = _now()
    db = get_sessionmaker()()
    try:
        row = ExportJob(
            tenant_id=int(_tid()),
            module_code=MODULE_CODE,
            export_type=EXPORT_TYPE,
            purpose=purpose,
            adapter_type=ADAPTER_TYPE,
            adapter_ref=uuid.uuid4().hex,
            filter_snapshot_json={"scope": scope},
            data_scope_snapshot_json={"user": _safe_user_snapshot(actor)},
            status="CREATED",
            progress=0,
            row_count=int(total or 0),
            expires_at=now + timedelta(hours=_TTL_HOURS),
            operator_id=actor_id,
            created_by=actor_id,
            result_json={
                "attempts": 0,
                "scope": scope,
                "requestedAt": now.isoformat(timespec="seconds"),
            },
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        data = _export_row(row)
        data.update({"taskId": str(row.id), "jobId": str(row.id), "queued": True, "scope": scope})
        return data
    finally:
        db.close()


def get_job(job_id: str, *, user=None) -> dict:
    _require_db()
    _require_manage(user)
    from app.services import data_exchange_job_service as jobs

    data = jobs.get_export_job(job_id, user=_user(user), module_code=MODULE_CODE)
    data.update({"taskId": data["id"], "jobId": data["id"]})
    return data


def create_download_ticket(job_id: str, expected_version: int, *, user=None) -> dict:
    _require_db()
    _require_manage(user)
    from app.services import data_exchange_job_service as jobs

    result = jobs.create_download_ticket(
        job_id, expected_version=expected_version, user=_user(user)
    )
    result["downloadUrl"] = (
        f"/api/v1/approvals/export/{job_id}/download?ticket={result['ticket']}"
    )
    return result


def consume_download_ticket(job_id: str, ticket: str, *, user=None):
    _require_db()
    _require_manage(user)
    from app.services import data_exchange_job_service as jobs

    return jobs.consume_download_ticket(job_id, ticket, user=_user(user))


def _claim(limit: int, *, worker_id: str = _WORKER_ID) -> list[dict]:
    now = _now()
    stale_before = now - timedelta(seconds=_LEASE_SECONDS)
    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(ExportJob).where(
            ExportJob.tenant_id == _tid(),
            ExportJob.module_code == MODULE_CODE,
            ExportJob.adapter_type == ADAPTER_TYPE,
            ExportJob.is_deleted.is_(False),
            or_(
                ExportJob.status.in_(("CREATED", "FAILED")),
                and_(ExportJob.status == "RUNNING", ExportJob.updated_at <= stale_before),
            ),
        ).order_by(ExportJob.created_at, ExportJob.id)
         .with_for_update(skip_locked=True).limit(max(1, min(20, int(limit or 1))))).all()
        claimed: list[dict] = []
        for row in rows:
            result = dict(row.result_json or {})
            attempts = int(result.get("attempts") or 0)
            if attempts >= _MAX_ATTEMPTS:
                row.status = "DEAD"
                row.error_message = row.error_message or "审批导出重试次数已耗尽"
                row.finished_at = now
                row.version = int(row.version or 0) + 1
                continue
            lease = uuid.uuid4().hex
            result.update({
                "attempts": attempts + 1,
                "workerId": worker_id,
                "leaseToken": lease,
                "leaseUntil": (now + timedelta(seconds=_LEASE_SECONDS)).isoformat(timespec="seconds"),
            })
            row.status = "RUNNING"
            row.progress = max(1, int(row.progress or 0))
            row.error_message = None
            row.result_json = result
            row.version = int(row.version or 0) + 1
            claimed.append({
                "id": int(row.id),
                "tenantId": int(row.tenant_id),
                "leaseToken": lease,
                "scope": str((row.filter_snapshot_json or {}).get("scope") or "").upper(),
                "purpose": str(row.purpose or ""),
                "user": dict((row.data_scope_snapshot_json or {}).get("user") or {}),
                "total": int(row.row_count or 0),
            })
        db.commit()
        return claimed
    finally:
        db.close()


def _update_progress(job_id: int, tenant_id: int, lease_token: str, processed: int, total: int) -> None:
    db = get_sessionmaker()()
    try:
        row = db.get(ExportJob, int(job_id))
        result = dict(row.result_json or {}) if row else {}
        if (not row or int(row.tenant_id) != int(tenant_id) or row.status != "RUNNING"
                or result.get("leaseToken") != lease_token):
            return
        row.progress = 95 if total <= 0 else min(95, max(1, int(processed * 95 / total)))
        result["processedRows"] = int(processed)
        result["leaseUntil"] = (_now() + timedelta(seconds=_LEASE_SECONDS)).isoformat(timespec="seconds")
        row.result_json = result
        row.version = int(row.version or 0) + 1
        db.commit()
    finally:
        db.close()


def _generate(item: dict) -> tuple[int, int]:
    tenant_id = int(item["tenantId"])
    user = dict(item.get("user") or {})
    scope = str(item.get("scope") or "").upper()
    purpose = str(item.get("purpose") or "")
    total = int(item.get("total") or 0)
    page = 1
    processed = 0
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("审批中心")
    ws.append([
        f"导出人：{user.get('realName') or user.get('loginName') or '系统'}",
        f"租户：{tenant_id}",
        f"范围：{scope}",
        f"用途：{purpose}",
        f"导出时间：{_now():%Y-%m-%d %H:%M:%S}",
    ])
    ws.append([title for _key, title in _COLUMNS])

    previous_tenant = get_tenant()
    previous_user = get_current_user_ctx()
    set_tenant({"tenantId": str(tenant_id)})
    set_current_user(user)
    try:
        while True:
            rows, authoritative_total = _load_page(scope, page, _PAGE_SIZE, user=user)
            if page == 1:
                total = int(authoritative_total or 0)
            if not rows:
                break
            for row in rows:
                ws.append([_cell(row, key) for key, _title in _COLUMNS])
            processed += len(rows)
            _update_progress(item["id"], tenant_id, item["leaseToken"], processed, total)
            if processed >= total or len(rows) < _PAGE_SIZE:
                break
            page += 1
        output = BytesIO()
        wb.save(output)
        file_id = _write_generated_file(
            output.getvalue(),
            f"审批中心_{scope}_{_now():%Y%m%d_%H%M%S}.xlsx",
            biz_id=f"approval-export:{item['id']}",
            user=user,
            security_level="SENSITIVE",
        )
        return int(file_id), int(processed)
    finally:
        set_current_user(previous_user)
        set_tenant(previous_tenant)


def _finish(job_id: int, tenant_id: int, lease_token: str, *, file_id: int | None = None,
            row_count: int = 0, error: str = "") -> bool:
    now = _now()
    db = get_sessionmaker()()
    try:
        row = db.get(ExportJob, int(job_id))
        result = dict(row.result_json or {}) if row else {}
        if (not row or int(row.tenant_id) != int(tenant_id) or row.status != "RUNNING"
                or result.get("leaseToken") != lease_token):
            return False
        result.pop("leaseToken", None)
        result.pop("leaseUntil", None)
        result.pop("workerId", None)
        if file_id:
            row.status = "SUCCEEDED"
            row.progress = 100
            row.row_count = int(row_count)
            row.file_object_id = int(file_id)
            row.finished_at = now
            row.error_message = None
            result.update({"fileObjectId": str(file_id), "completedRows": int(row_count)})
        else:
            attempts = int(result.get("attempts") or 0)
            row.status = "DEAD" if attempts >= _MAX_ATTEMPTS else "FAILED"
            row.progress = 0
            row.error_message = str(error or "审批导出失败")[:4000]
            if row.status == "DEAD":
                row.finished_at = now
        row.result_json = result
        row.version = int(row.version or 0) + 1
        db.commit()
        return True
    finally:
        db.close()


def run_pending(limit: int = 2, *, worker_id: str = _WORKER_ID) -> dict:
    """scheduler 调用：领取 CREATED/FAILED/失租 RUNNING，自动重试并隔离单任务失败。"""
    claimed = _claim(limit, worker_id=worker_id)
    succeeded = failed = 0
    for item in claimed:
        try:
            file_id, row_count = _generate(item)
            succeeded += int(_finish(
                item["id"], item["tenantId"], item["leaseToken"],
                file_id=file_id, row_count=row_count,
            ))
        except Exception as exc:  # noqa: BLE001
            _finish(
                item["id"], item["tenantId"], item["leaseToken"],
                error=f"{type(exc).__name__}: {exc}",
            )
            failed += 1
    return {"claimed": len(claimed), "succeeded": succeeded, "failed": failed}
