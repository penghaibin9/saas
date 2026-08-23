"""Task-scoped attachment Reader authority for the generic approval center.

Approval attachment access is derived from the concrete workflow task + source business relation.
It must not fall back to a public URL or infer source-module permission in the browser.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import jwt
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.core.redis_client import cache_set_json_if_absent
from app.models import WorkflowInstance, WorkflowTask
from app.models.file import FileBinding, FileObject, FileVersion
from app.services import approval_runtime_service as runtime
from app.services.db_service import _tid, session
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

PREVIEW_TTL_SECONDS = 180
DOWNLOAD_TTL_SECONDS = 60
TICKET_TYPE = "approval-attachment-ticket"

STATUS_TEXT = {
    "NOT_REQUIRED": "无需扫描",
    "PENDING": "等待安全扫描",
    "RUNNING": "正在安全扫描",
    "CLEAN": "安全可用",
    "INFECTED": "检测到风险，已拒绝",
    "ERROR": "安全扫描失败",
}


def _actor(user: dict | None) -> str:
    value = resolve_message_user_id(user or {}) or (user or {}).get("userId") or (user or {}).get("sub")
    return str(value or "")


def _normalized_action(action: str) -> str:
    value = str(action or "").strip().lower()
    if value not in {"preview", "download"}:
        raise AppException("VALIDATION_ERROR", "附件动作仅支持 preview/download")
    return value


def _task_scope(task_id: str, user: dict) -> tuple[int, str, str]:
    """Validate the task with the same approval authority, then resolve immutable source coordinates."""
    runtime.get_task(task_id, user=user)
    try:
        task_id_int = int(task_id)
    except (TypeError, ValueError):
        raise not_found("审批附件不存在")
    with session() as db:
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.id == task_id_int,
            WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False),
        )).first()
        if not task:
            raise not_found("审批附件不存在")
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == task.instance_id,
            WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False),
        )).first()
        if not inst:
            raise not_found("审批附件不存在")
        return int(inst.id), str(inst.source_biz_type or "").upper(), str(inst.source_biz_id or "")


def _ready(file_obj: FileObject) -> bool:
    scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
    return bool(is_downloadable_status(file_obj.status) and scan in READY_SCAN_STATES)


def _load_scope_files(db, source_biz_type: str, source_biz_id: str):
    bindings = db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == _tid(),
        FileBinding.biz_type == source_biz_type,
        FileBinding.biz_id == source_biz_id,
        FileBinding.is_current.is_(True),
        FileBinding.status == "ACTIVE",
        FileBinding.is_deleted.is_(False),
    ).order_by(FileBinding.id)).all()
    binding_by_file = {int(item.file_id): item for item in bindings}

    conditions = []
    if binding_by_file:
        conditions.append(FileObject.id.in_(binding_by_file.keys()))
    # Legacy uploads may predate FileBinding. Exact source coordinates still form the task relation.
    conditions.append((FileObject.biz_type == source_biz_type) & (FileObject.biz_id == source_biz_id))
    files = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(),
        FileObject.is_deleted.is_(False),
        or_(*conditions),
    ).order_by(FileObject.created_at, FileObject.id)).all()
    return list(files), binding_by_file


def list_attachments(task_id: str, user: dict) -> list[dict]:
    _, source_biz_type, source_biz_id = _task_scope(task_id, user)
    if not source_biz_type or not source_biz_id:
        return []
    with session() as db:
        files, binding_by_file = _load_scope_files(db, source_biz_type, source_biz_id)
        version_ids = {int(b.version_id) for b in binding_by_file.values() if b.version_id}
        versions = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(),
            FileVersion.id.in_(version_ids),
            FileVersion.is_deleted.is_(False),
        )).all() if version_ids else []
        version_by_id = {int(v.id): v for v in versions}

        rows = []
        for file_obj in files:
            binding = binding_by_file.get(int(file_obj.id))
            version = version_by_id.get(int(binding.version_id)) if binding and binding.version_id else None
            scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
            usable = _ready(file_obj)
            rows.append({
                "fileId": str(file_obj.id),
                "fileName": file_obj.file_name,
                "ext": file_obj.ext or "",
                "mimeType": file_obj.mime_type or "",
                "sizeBytes": int(file_obj.size_bytes or 0),
                "scanStatus": scan,
                "statusText": STATUS_TEXT.get(scan, "状态未知"),
                "readyForBusiness": usable,
                "allowedActions": ["viewMetadata", "preview", "download"] if usable else ["viewMetadata"],
                "fileVersionId": str(version.id) if version else None,
                "versionNo": int(version.version_no) if version else (int(binding.version_no) if binding else None),
                "sourceSha256": file_obj.sha256 or "",
            })
        return rows


def _resolve_attachment(task_id: str, file_id: int, user: dict, *, action: str) -> tuple[FileObject, Path]:
    _normalized_action(action)
    _, source_biz_type, source_biz_id = _task_scope(task_id, user)
    with session() as db:
        files, _ = _load_scope_files(db, source_biz_type, source_biz_id)
        file_obj = next((item for item in files if int(item.id) == int(file_id)), None)
        if not file_obj or not _ready(file_obj):
            raise not_found("审批附件不存在")
        path = get_backend().fetch_local(file_obj.file_key)
        if not path or not path.exists():
            raise not_found("审批附件不存在")
        return file_obj, path


def issue_ticket(task_id: str, file_id: int, action: str, user: dict) -> dict:
    normalized = _normalized_action(action)
    _resolve_attachment(task_id, int(file_id), user, action=normalized)
    now = int(time.time())
    ttl = PREVIEW_TTL_SECONDS if normalized == "preview" else DOWNLOAD_TTL_SECONDS
    token = jwt.encode({
        "typ": TICKET_TYPE,
        "jti": uuid.uuid4().hex,
        "tenantId": int(_tid()),
        "taskId": str(task_id),
        "fileId": int(file_id),
        "action": normalized,
        "actor": _actor(user),
        "iat": now,
        "exp": now + ttl,
    }, settings.JWT_SECRET, algorithm=settings.JWT_ALG)
    return {
        "ticket": token,
        "action": normalized,
        "expiresIn": ttl,
        "singleUse": normalized == "download",
        "url": f"/api/v1/approvals/tasks/{task_id}/files/{int(file_id)}/{normalized}?ticket={token}",
    }


def consume_ticket(task_id: str, file_id: int, action: str, ticket: str, user: dict) -> tuple[Path, str, str | None]:
    normalized = _normalized_action(action)
    try:
        payload = jwt.decode(str(ticket or ""), settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except Exception:
        raise not_found("审批附件不存在")
    if (
        payload.get("typ") != TICKET_TYPE
        or int(payload.get("tenantId") or 0) != int(_tid())
        or str(payload.get("taskId") or "") != str(task_id)
        or int(payload.get("fileId") or 0) != int(file_id)
        or str(payload.get("action") or "") != normalized
        or str(payload.get("actor") or "") != _actor(user)
    ):
        raise not_found("审批附件不存在")

    file_obj, path = _resolve_attachment(task_id, int(file_id), user, action=normalized)
    if normalized == "download":
        ttl = max(1, int(payload.get("exp") or 0) - int(time.time()))
        acquired = cache_set_json_if_absent(
            f"approval-attachment-ticket:used:{_tid()}:{payload.get('jti')}",
            {"usedAt": int(time.time()), "actor": _actor(user), "taskId": str(task_id), "fileId": int(file_id)},
            ttl,
        )
        if acquired is False:
            raise not_found("下载票据不存在或已失效")
        if acquired is None:
            raise AppException("TICKET_STORE_UNAVAILABLE", "下载票据存储不可用，请稍后重试", http_status=503)
    return path, file_obj.file_name, file_obj.mime_type


__all__ = ["consume_ticket", "issue_ticket", "list_attachments"]
