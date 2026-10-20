"""资助发放台账异步 XLSX 导出。

Web 请求只冻结筛选、导出用途、操作者和学工 data scope，并创建 ExportJob；
独立 scheduler 分页读取与 Staff PC 同一 ``list_disbursements`` 投影后生成 XLSX。
因此导出不会绕过资助发放的数据范围/金额脱敏，也不会在 Web worker 内同步扫描大台账。
"""
from __future__ import annotations

import json
import socket
import uuid
from datetime import datetime, timedelta
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import and_, or_, select

from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.data_exchange import ExportJob
from app.services.data_exchange_job_service import _export_row, _write_generated_file
from app.services.db_service import _tid
from app.services.message_identity import resolve_message_user_id

MODULE_CODE = "STUDENT_AFFAIRS"
EXPORT_TYPE = "FUNDING_DISBURSEMENT_XLSX"
ADAPTER_TYPE = "STUDENT_AFFAIRS_FUNDING_DISBURSEMENT"
_MAX_ATTEMPTS = 5
_LEASE_SECONDS = 10 * 60
_PAGE_SIZE = 500
_TTL_HOURS = 24
_WORKER_ID = f"{socket.gethostname()}:{uuid.uuid4().hex[:12]}"

_COLUMNS = (
    ("studentNo", "学号"),
    ("realName", "姓名"),
    ("projectType", "项目类型"),
    ("amount", "发放金额"),
    ("bankLast4", "银行卡后4位"),
    ("bankStatusLabel", "发放状态"),
    ("disburseNo", "发放批次号"),
    ("issuedAt", "发放时间"),
    ("failReason", "失败原因"),
)
_ALLOWED_BANK_STATUS = {"", "PENDING", "ISSUED", "FAILED", "RETURNED"}


def _now() -> datetime:
    return datetime.utcnow()


def _actor_id(user: dict) -> int | None:
    return resolve_message_user_id(user or {}) or None


def _safe_user_snapshot(user: dict) -> dict:
    """只持久化重建权限/范围所需声明，不保存 token、密码或请求头。"""
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


def _normalize(batch_id=None, bank_status=None, purpose=None) -> tuple[int | None, str, str]:
    try:
        batch = int(batch_id) if batch_id not in (None, "") else None
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "批次编号格式不正确", http_status=400) from exc
    if batch is not None and batch <= 0:
        raise AppException("VALIDATION_ERROR", "批次编号必须大于 0", http_status=400)
    status = str(bank_status or "").strip().upper()
    if status not in _ALLOWED_BANK_STATUS:
        raise AppException("VALIDATION_ERROR", "未知发放状态", http_status=400)
    purpose_text = str(purpose or "").strip()
    if len(purpose_text) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填且不少于 5 字", http_status=400)
    return batch, status, purpose_text


def _excel_safe(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if stripped.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def create_job(user: dict, *, batch_id=None, bank_status=None, purpose=None) -> dict:
    """创建异步导出任务；请求线程只执行 count + 一行范围核验。"""
    from app.services import affairs_funding_service as funding

    batch, status, purpose_text = _normalize(batch_id, bank_status, purpose)
    actor = dict(user or get_current_user_ctx() or {})
    _sample, total = funding.list_disbursements(
        actor, batch, status or None, page=1, page_size=1,
    )
    actor_id = _actor_id(actor)
    now = _now()
    db = get_sessionmaker()()
    try:
        row = ExportJob(
            tenant_id=int(_tid()),
            module_code=MODULE_CODE,
            export_type=EXPORT_TYPE,
            purpose=purpose_text,
            adapter_type=ADAPTER_TYPE,
            adapter_ref=uuid.uuid4().hex,
            filter_snapshot_json={"batchId": batch, "bankStatus": status},
            data_scope_snapshot_json={"user": _safe_user_snapshot(actor)},
            status="CREATED",
            progress=0,
            row_count=int(total or 0),
            expires_at=now + timedelta(hours=_TTL_HOURS),
            operator_id=actor_id,
            created_by=actor_id,
            result_json={"attempts": 0, "requestedAt": now.isoformat(timespec="seconds")},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        data = _export_row(row)
        data.update({"jobId": str(row.id), "queued": True})
        job_id = int(row.id)
    finally:
        db.close()

    from app.services.db_service import audit_insert
    audit_insert(
        "SENSITIVE_EXPORT",
        "funding_disbursement_ledger",
        {
            "jobId": str(job_id),
            "rows": int(total or 0),
            "purpose": purpose_text,
            "batchId": str(batch or ""),
            "bankStatus": status,
            "status": "QUEUED",
        },
        "SUCCESS",
    )
    return data


def get_job(job_id: str, user: dict) -> dict:
    from app.services import data_exchange_job_service as jobs

    data = jobs.get_export_job(job_id, user=user, module_code=MODULE_CODE)
    data["jobId"] = data["id"]
    return data


def create_download_ticket(job_id: str, expected_version: int, user: dict) -> dict:
    from app.services import data_exchange_job_service as jobs

    result = jobs.create_download_ticket(job_id, expected_version=expected_version, user=user)
    result["downloadUrl"] = (
        f"/api/v1/student-affairs/funding/disbursements/export-jobs/{job_id}/download"
        f"?ticket={result['ticket']}"
    )
    return result


def consume_download_ticket(job_id: str, ticket: str, user: dict):
    from app.services import data_exchange_job_service as jobs

    return jobs.consume_download_ticket(job_id, ticket, user=user)


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
         .with_for_update(skip_locked=True)
         .limit(max(1, min(20, int(limit or 1))))).all()
        claimed: list[dict] = []
        for row in rows:
            result = dict(row.result_json or {})
            attempts = int(result.get("attempts") or 0)
            if attempts >= _MAX_ATTEMPTS:
                row.status = "DEAD"
                row.error_message = row.error_message or "资助发放台账导出重试次数已耗尽"
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
            filters = dict(row.filter_snapshot_json or {})
            claimed.append({
                "id": int(row.id),
                "tenantId": int(row.tenant_id),
                "leaseToken": lease,
                "batchId": filters.get("batchId"),
                "bankStatus": str(filters.get("bankStatus") or ""),
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
    from app.services import affairs_funding_service as funding

    tenant_id = int(item["tenantId"])
    user = dict(item.get("user") or {})
    batch_id = item.get("batchId")
    bank_status = str(item.get("bankStatus") or "") or None
    purpose = str(item.get("purpose") or "")
    total = int(item.get("total") or 0)
    processed = 0
    page = 1

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("资助发放台账")
    ws.append([
        _excel_safe(f"导出人：{user.get('realName') or user.get('loginName') or '系统'}"),
        _excel_safe(f"租户：{tenant_id}"),
        _excel_safe(f"批次：{batch_id or '全部'}"),
        _excel_safe(f"状态：{bank_status or '全部'}"),
        _excel_safe(f"用途：{purpose}"),
        _excel_safe(f"导出时间：{_now():%Y-%m-%d %H:%M:%S}"),
    ])
    ws.append([title for _key, title in _COLUMNS])

    previous_tenant = get_tenant()
    previous_user = get_current_user_ctx()
    set_tenant({"tenantId": str(tenant_id)})
    set_current_user(user)
    try:
        while True:
            rows, authoritative_total = funding.list_disbursements(
                user, batch_id, bank_status, page=page, page_size=_PAGE_SIZE,
            )
            if page == 1:
                total = int(authoritative_total or 0)
            if not rows:
                break
            for row in rows:
                ws.append([_excel_safe(row.get(key, "")) for key, _title in _COLUMNS])
            processed += len(rows)
            _update_progress(item["id"], tenant_id, item["leaseToken"], processed, total)
            if processed >= total or len(rows) < _PAGE_SIZE:
                break
            page += 1
        output = BytesIO()
        wb.save(output)
        file_id = _write_generated_file(
            output.getvalue(),
            f"资助发放台账_{_now():%Y%m%d_%H%M%S}.xlsx",
            biz_id=f"funding-disbursement-export:{item['id']}",
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
            row.error_message = str(error or "资助发放台账导出失败")[:4000]
            if row.status == "DEAD":
                row.finished_at = now
        row.result_json = result
        row.version = int(row.version or 0) + 1
        db.commit()
        return True
    finally:
        db.close()


def run_pending(limit: int = 2, *, worker_id: str = _WORKER_ID) -> dict:
    claimed = _claim(limit, worker_id=worker_id)
    succeeded = failed = 0
    for item in claimed:
        try:
            file_id, row_count = _generate(item)
            completed = _finish(
                item["id"], item["tenantId"], item["leaseToken"],
                file_id=file_id, row_count=row_count,
            )
            succeeded += int(completed)
            if completed:
                from app.services.db_service import audit_insert
                audit_insert(
                    "SENSITIVE_EXPORT",
                    "funding_disbursement_ledger",
                    {
                        "jobId": str(item["id"]),
                        "rows": int(row_count),
                        "purpose": item.get("purpose") or "",
                        "status": "SUCCEEDED",
                    },
                    "SUCCESS",
                )
        except Exception as exc:  # noqa: BLE001 - 单任务失败不得终止其他租户任务
            _finish(
                item["id"], item["tenantId"], item["leaseToken"],
                error=f"{type(exc).__name__}: {exc}",
            )
            failed += 1
    return {"claimed": len(claimed), "succeeded": succeeded, "failed": failed}
