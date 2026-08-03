"""请假台账异步导出。

Web 请求只冻结筛选条件、操作者与数据范围快照并创建 ``ExportJob``；独立 scheduler
分页读取数据并生成 XLSX。任务详情和下载继续复用统一数据交换任务/一次性票据底座。
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
from app.services.message_identity import resolve_message_user_id
from app.services.db_service import _tid

MODULE_CODE = "STUDENT_AFFAIRS"
EXPORT_TYPE = "LEAVE_LEDGER_XLSX"
ADAPTER_TYPE = "STUDENT_AFFAIRS_LEAVE"
_MAX_ATTEMPTS = 5
_LEASE_SECONDS = 10 * 60
_PAGE_SIZE = 500
_TTL_HOURS = 24
_WORKER_ID = f"{socket.gethostname()}:{uuid.uuid4().hex[:12]}"

_COLUMNS = (
    ("studentNo", "学号"),
    ("studentName", "姓名"),
    ("className", "班级"),
    ("leaveTypeLabel", "请假类型"),
    ("days", "天数"),
    ("startTime", "开始时间"),
    ("endTime", "结束时间"),
    ("expectedReturnAt", "应返校时间"),
    ("actualReturnAt", "实际返校时间"),
    ("affairsStatusLabel", "状态"),
    ("reason", "事由"),
)


def _now() -> datetime:
    return datetime.utcnow()


def _actor_id(user: dict) -> int | None:
    return resolve_message_user_id(user or {}) or None


def _safe_user_snapshot(user: dict) -> dict:
    """只保存重建权限和范围所需声明，不保存 token、密码或请求头。"""
    allowed = {
        "userId", "sub", "loginName", "realName", "userType", "currentRoleCode",
        "activeContextId", "permissions", "permissionCodes", "roles", "roleCodes",
        "dataScope", "dataScopes", "scopeType", "scopeIds", "tenantId",
    }
    snapshot: dict = {}
    for key in allowed:
        value = (user or {}).get(key)
        if value is not None:
            try:
                json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                continue
            snapshot[key] = value
    return snapshot


def _filters(**kwargs) -> dict:
    return {
        "status": kwargs.get("status"),
        "leaveType": kwargs.get("leave_type"),
        "classId": kwargs.get("class_id"),
        "keyword": kwargs.get("keyword"),
        "studentId": kwargs.get("student_id"),
        "dateStart": kwargs.get("date_start"),
        "dateEnd": kwargs.get("date_end"),
        "followupOnly": bool(kwargs.get("followup_only")),
    }


def create_job(
    user: dict,
    status=None,
    leave_type=None,
    class_id=None,
    keyword=None,
    date_start=None,
    date_end=None,
    *,
    followup_only: bool = False,
    student_id=None,
) -> dict:
    """创建异步导出任务；不得在请求线程读取全量数据或生成工作簿。"""
    from app.services import affairs_leave_service as leave
    from app.services.db_service import _tid

    filter_snapshot = _filters(
        status=status, leave_type=leave_type, class_id=class_id, keyword=keyword,
        student_id=student_id, date_start=date_start, date_end=date_end,
        followup_only=followup_only,
    )
    # 只执行 count + 1 行权限/范围验证，耗时与导出行数无关。
    _sample, total = leave.list_leaves(
        user, status, leave_type, class_id, keyword, date_start, date_end,
        followup_only=followup_only, page=1, page_size=1, student_id=student_id,
    )
    actor_id = _actor_id(user)
    now = _now()
    db = get_sessionmaker()()
    try:
        row = ExportJob(
            tenant_id=int(_tid()), module_code=MODULE_CODE, export_type=EXPORT_TYPE,
            purpose="请假台账导出", adapter_type=ADAPTER_TYPE,
            adapter_ref=uuid.uuid4().hex,
            filter_snapshot_json=filter_snapshot,
            data_scope_snapshot_json={"user": _safe_user_snapshot(user)},
            status="CREATED", progress=0, row_count=int(total),
            expires_at=now + timedelta(hours=_TTL_HOURS),
            operator_id=actor_id, created_by=actor_id,
            result_json={"attempts": 0, "requestedAt": now.isoformat(timespec="seconds")},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        job_id = int(row.id)
        data = _export_row(row)
        data.update({"jobId": str(row.id), "queued": True})
    finally:
        db.close()

    # 请求阶段即留痕；完成阶段由任务状态、文件对象和下载票据继续形成证据链。
    from app.services.db_service import audit_insert, session
    from app.services import affairs_leave_service as leave
    with session() as audit_db:
        leave._audit(audit_db, None, "EXPORT_REQUESTED", f"jobId={job_id};rows={int(total)}")
        audit_db.commit()
    audit_insert(
        "SENSITIVE_EXPORT", "leave_ledger",
        {"jobId": str(job_id), "rows": int(total), "status": "QUEUED", "filters": filter_snapshot},
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
        f"/api/v1/student-affairs/leave/export-jobs/{job_id}/download"
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
         .with_for_update(skip_locked=True).limit(max(1, min(20, int(limit or 1))))).all()
        claimed: list[dict] = []
        for row in rows:
            result = dict(row.result_json or {})
            attempts = int(result.get("attempts") or 0)
            if attempts >= _MAX_ATTEMPTS:
                row.status = "DEAD"
                row.error_message = row.error_message or "导出任务重试次数已耗尽"
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
                "id": int(row.id), "tenantId": int(row.tenant_id), "leaseToken": lease,
                "filters": dict(row.filter_snapshot_json or {}),
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
        progress = 95 if total <= 0 else min(95, max(1, int(processed * 95 / total)))
        row.progress = progress
        result["processedRows"] = int(processed)
        result["leaseUntil"] = (_now() + timedelta(seconds=_LEASE_SECONDS)).isoformat(timespec="seconds")
        row.result_json = result
        row.version = int(row.version or 0) + 1
        db.commit()
    finally:
        db.close()


def _generate(item: dict) -> tuple[int, int]:
    from app.core.context import set_tenant
    from app.services import affairs_leave_service as leave

    tenant_id = int(item["tenantId"])
    user = dict(item.get("user") or {})
    filters = dict(item.get("filters") or {})
    total = int(item.get("total") or 0)
    page = 1
    processed = 0
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("请假台账")
    ws.append([
        f"导出人：{user.get('realName') or user.get('loginName') or '系统'}",
        f"租户：{tenant_id}",
        f"导出时间：{_now():%Y-%m-%d %H:%M:%S}",
    ])
    ws.append([title for _key, title in _COLUMNS])
    previous_tenant = get_tenant()
    previous_user = get_current_user_ctx()
    set_tenant({"tenantId": str(tenant_id)})
    set_current_user(user)
    try:
        while True:
            rows, authoritative_total = leave.list_leaves(
                user,
                filters.get("status"), filters.get("leaveType"), filters.get("classId"),
                filters.get("keyword"), filters.get("dateStart"), filters.get("dateEnd"),
                followup_only=bool(filters.get("followupOnly")),
                page=page, page_size=_PAGE_SIZE, student_id=filters.get("studentId"),
            )
            if page == 1:
                total = int(authoritative_total)
            if not rows:
                break
            for row in rows:
                ws.append([row.get(key, "") for key, _title in _COLUMNS])
            processed += len(rows)
            _update_progress(item["id"], tenant_id, item["leaseToken"], processed, total)
            if processed >= total or len(rows) < _PAGE_SIZE:
                break
            page += 1
        output = BytesIO()
        wb.save(output)
        file_id = _write_generated_file(
            output.getvalue(), "请假台账.xlsx", biz_id=f"leave-export:{item['id']}",
            user=user, security_level="SENSITIVE",
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
            row.error_message = str(error or "导出任务失败")[:4000]
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
            succeeded += int(_finish(
                item["id"], item["tenantId"], item["leaseToken"],
                file_id=file_id, row_count=row_count,
            ))
        except Exception as exc:  # noqa: BLE001 - 单任务失败不得终止其他租户/任务
            _finish(
                item["id"], item["tenantId"], item["leaseToken"],
                error=f"{type(exc).__name__}: {exc}",
            )
            failed += 1
    return {"claimed": len(claimed), "succeeded": succeeded, "failed": failed}
