"""审批中心导出任务：先持久化 PENDING，再后台执行 RUNNING -> SUCCESS/FAILED。"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from app.core.context import (
    current_tenant_id,
    get_current_user_ctx,
    get_tenant,
    set_current_user,
    set_tenant,
)
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.db.session import db_enabled
from app.services.message_identity import resolve_message_user_id


_ALLOWED_SCOPES = {"TODO", "DONE", "RETURNED", "CC", "TEMPLATE"}
_MAX_ROWS = 5000


def _require_db() -> None:
    if not db_enabled():
        raise AppException(
            "APPROVAL_BACKEND_UNAVAILABLE",
            "审批导出需要真实数据库，当前不可产生假成功",
            http_status=503,
        )


def _user(user=None) -> dict:
    return dict(user or get_current_user_ctx() or {})


def _tenant_id() -> int:
    try:
        value = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        value = 0
    if not value:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文", http_status=400)
    return value


def _require_manage(user=None) -> None:
    actor = _user(user)
    if not (has_permission(actor, "*") or has_permission(actor, "approval.manage")):
        raise no_permission("无审批中心管理权限（approval.manage）")


def _normalize(scope, purpose) -> tuple[str, str]:
    normalized_scope = str(scope or "").strip().upper()
    if normalized_scope not in _ALLOWED_SCOPES:
        raise AppException("VALIDATION_ERROR", "未知审批导出范围", http_status=400)
    normalized_purpose = str(purpose or "").strip()
    if len(normalized_purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填且不少于 5 字", http_status=400)
    return normalized_scope, normalized_purpose


def _response(task, scope: str | None = None) -> dict:
    condition = task.condition_json if isinstance(task.condition_json, dict) else {}
    resolved_scope = scope or str(condition.get("scope") or "")
    status = str(task.status or "PENDING").upper()
    return {
        "taskId": str(task.id),
        "status": status,
        "scope": resolved_scope,
        "rowCount": int(task.row_count or 0),
        "error": str(task.remark or "") if status == "FAILED" else None,
        "downloadUrl": (
            f"/api/v1/approvals/export/{task.id}/download" if status == "SUCCESS" else None
        ),
        "createdAt": task.created_at.isoformat(timespec="seconds") if task.created_at else None,
        "updatedAt": task.updated_at.isoformat(timespec="seconds") if task.updated_at else None,
    }


def create_job(scope, purpose, *, user=None) -> dict:
    """只创建任务，不在请求线程生成文件。"""
    _require_db()
    _require_manage(user)
    scope, purpose = _normalize(scope, purpose)
    from app.models import ExportTask
    from app.services import db_service

    actor = _user(user)
    uid = resolve_message_user_id(actor) or None
    with db_service.session() as db:
        task = ExportTask(
            tenant_id=_tenant_id(),
            export_mode="LIST",
            module_code="approval",
            condition_json={"scope": scope},
            field_list_json={
                "columns": ["id", "title", "bizType", "status", "actedAt", "reason"]
            },
            row_count=0,
            purpose=purpose,
            file_hash=None,
            status="PENDING",
            remark=None,
            created_by=uid,
            updated_by=uid,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return _response(task, scope)


def _load_rows(scope: str, *, user=None):
    from app.services import approval_returned_service as returned_service
    from app.services import approval_runtime_service as runtime
    from app.services import approval_template_service as template_service

    if scope == "TODO":
        return runtime.list_tasks(1, _MAX_ROWS, user=user)
    if scope == "DONE":
        return runtime.list_processed(1, _MAX_ROWS, user=user)
    if scope == "RETURNED":
        return returned_service.list_returned(1, _MAX_ROWS, user=user)
    if scope == "CC":
        return runtime.list_cc(1, _MAX_ROWS, user=user)
    return template_service.list_templates(1, _MAX_ROWS, user=user)


def _write_xlsx(scope: str, purpose: str, rows: list[dict], *, user=None) -> tuple[str, str]:
    from openpyxl import Workbook
    from app.services.import_export_service import upload_dir

    actor = _user(user)
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title="审批中心")
    ws.append([
        f"审批中心 · {scope} · 导出人：{actor.get('realName') or actor.get('real_name') or '-'} "
        f"· 时间：{datetime.now():%Y-%m-%d %H:%M} · 用途：{purpose}"
    ])
    ws.append(["任务/模板ID", "标题/名称", "业务类型", "状态", "办理时间", "原因/说明"])
    for row in rows:
        ws.append([
            str(row.get("taskId") or row.get("id") or ""),
            str(row.get("title") or row.get("name") or ""),
            str(row.get("sourceBizType") or row.get("bizType") or ""),
            str(row.get("status") or row.get("rectifyStatus") or ""),
            str(row.get("actedAt") or row.get("updatedAt") or row.get("ccTime") or ""),
            str(row.get("actionReason") or row.get("reason") or row.get("ccReason") or ""),
        ])

    key = f"exports/{datetime.now():%Y%m%d}/approval_{scope.lower()}_{uuid.uuid4().hex[:8]}.xlsx"
    target = upload_dir() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    wb.save(target)
    return key, hashlib.sha256(target.read_bytes()).hexdigest()


def run_job(task_id: str, *, tenant: dict, user: dict) -> None:
    """FastAPI BackgroundTasks 执行入口；状态始终落库，异常转 FAILED。"""
    previous_tenant = get_tenant()
    previous_user = get_current_user_ctx()
    set_tenant(dict(tenant or {}))
    set_current_user(dict(user or {}))
    try:
        _require_db()
        from sqlalchemy import select
        from app.models import ExportTask
        from app.services import db_service
        from app.services import mock_audit_service as audit

        with db_service.session() as db:
            task = db.scalars(select(ExportTask).where(
                ExportTask.id == int(task_id),
                ExportTask.tenant_id == _tenant_id(),
                ExportTask.module_code == "approval",
            ).with_for_update()).first()
            if not task or str(task.status).upper() != "PENDING":
                return
            task.status = "RUNNING"
            task.remark = None
            task.version = int(task.version or 0) + 1
            db.commit()

        try:
            with db_service.session() as db:
                task = db.scalars(select(ExportTask).where(
                    ExportTask.id == int(task_id),
                    ExportTask.tenant_id == _tenant_id(),
                    ExportTask.module_code == "approval",
                )).first()
                if not task:
                    return
                condition = task.condition_json if isinstance(task.condition_json, dict) else {}
                scope = str(condition.get("scope") or "").upper()
                purpose = str(task.purpose or "")

            rows, total = _load_rows(scope, user=user)
            if int(total or 0) > _MAX_ROWS:
                raise AppException(
                    "APPROVAL_EXPORT_TOO_LARGE",
                    f"导出数据量 {total} 行超过单次上限 {_MAX_ROWS} 行，请缩小范围",
                    http_status=400,
                )
            key, file_hash = _write_xlsx(scope, purpose, rows, user=user)

            with db_service.session() as db:
                task = db.scalars(select(ExportTask).where(
                    ExportTask.id == int(task_id),
                    ExportTask.tenant_id == _tenant_id(),
                    ExportTask.module_code == "approval",
                ).with_for_update()).first()
                if not task:
                    return
                task.status = "SUCCESS"
                task.row_count = int(total or 0)
                task.file_hash = file_hash
                task.remark = key
                task.version = int(task.version or 0) + 1
                audit.record_critical(
                    "审批导出完成",
                    method="POST",
                    path="/api/v1/approvals/export",
                    status_code=200,
                    target_type="approval-export",
                    target_id=str(task.id),
                    detail={"scope": scope, "rows": int(total or 0), "purpose": purpose},
                    db=db,
                )
                db.commit()
        except Exception as exc:
            message = str(getattr(exc, "message", None) or exc or "导出失败")[:480]
            with db_service.session() as db:
                task = db.scalars(select(ExportTask).where(
                    ExportTask.id == int(task_id),
                    ExportTask.tenant_id == _tenant_id(),
                    ExportTask.module_code == "approval",
                ).with_for_update()).first()
                if task:
                    task.status = "FAILED"
                    task.remark = message
                    task.version = int(task.version or 0) + 1
                    audit.record_critical(
                        "审批导出失败",
                        method="POST",
                        path="/api/v1/approvals/export",
                        status_code=500,
                        target_type="approval-export",
                        target_id=str(task.id),
                        detail={"error": message},
                        db=db,
                    )
                    db.commit()
    finally:
        set_tenant(previous_tenant)
        set_current_user(previous_user)


def get_job(task_id: str, *, user=None) -> dict:
    _require_db()
    _require_manage(user)
    from sqlalchemy import select
    from app.models import ExportTask
    from app.services import db_service

    with db_service.session() as db:
        task = db.scalars(select(ExportTask).where(
            ExportTask.id == int(task_id),
            ExportTask.tenant_id == _tenant_id(),
            ExportTask.module_code == "approval",
        )).first()
        if not task:
            raise not_found("导出任务不存在")
        return _response(task)


def export_file_path(task_id: str, *, user=None) -> Path:
    _require_db()
    _require_manage(user)
    from sqlalchemy import select
    from app.models import ExportTask
    from app.services import db_service
    from app.services.import_export_service import upload_dir

    with db_service.session() as db:
        task = db.scalars(select(ExportTask).where(
            ExportTask.id == int(task_id),
            ExportTask.tenant_id == _tenant_id(),
            ExportTask.module_code == "approval",
        )).first()
        if not task:
            raise not_found("导出任务不存在")
        status = str(task.status or "").upper()
        if status != "SUCCESS":
            raise AppException(
                "APPROVAL_EXPORT_NOT_READY",
                "导出任务尚未完成" if status in {"PENDING", "RUNNING"} else "导出任务已失败，请重新发起",
                http_status=409,
            )
        path = upload_dir() / str(task.remark or "")
        if not task.remark or not path.exists():
            raise not_found("导出文件不存在或已清理")
        return path
