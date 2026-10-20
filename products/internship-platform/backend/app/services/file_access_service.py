"""Standalone file authorization service for internship business files."""
from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import db_enabled, get_sessionmaker
from app.models.file import FileBinding, FileObject
from app.services.message_identity import resolve_message_user_id

Resolver = Callable[[Any, Any, list[Any], dict, str], bool]
_RESOLVERS: dict[str, Resolver] = {}
READY_FILE_STATUS = {"AVAILABLE", "STORED", "CONFIRMED"}
READY_SCAN_STATES = {"CLEAN", "NOT_REQUIRED"}
STATUS_TEXT = {
    "NOT_REQUIRED": "无需扫描",
    "CLEAN": "安全",
    "PENDING": "待扫描",
    "SCANNING": "扫描中",
    "RUNNING": "扫描中",
    "INFECTED": "已拒绝",
    "ERROR": "扫描失败",
}


def register_file_resolver(*biz_types: str):
    normalized = tuple(str(x or "").strip().upper() for x in biz_types if str(x or "").strip())
    def deco(fn: Resolver):
        for biz in normalized:
            existing = _RESOLVERS.get(biz)
            if existing is not None and existing is not fn:
                raise RuntimeError(f"duplicate file resolver: {biz}")
            _RESOLVERS[biz] = fn
        return fn
    return deco


def _scan_ready(file_obj) -> bool:
    return (
        str(file_obj.status or "").upper() in READY_FILE_STATUS
        and str(file_obj.scan_status or "NOT_REQUIRED").upper() in READY_SCAN_STATES
    )


def _actor_id(user: dict) -> str:
    value = resolve_message_user_id(user or {}) or (user or {}).get("userId") or (user or {}).get("id") or ""
    return str(value).replace("db-", "").strip()


def _active_bindings(bindings):
    return [b for b in bindings if not b.is_deleted and str(b.status or "").upper() == "ACTIVE"]


def _student_identity_values(user: dict) -> set[str]:
    return {
        str((user or {}).get("studentId") or "").strip(),
        str((user or {}).get("studentNo") or "").strip(),
    } - {""}


def _scope_internship_ids(bindings) -> set[int]:
    out: set[int] = set()
    for binding in _active_bindings(bindings):
        for source in (binding.scope_json or {}, binding.data_scope_snapshot_json or {}):
            raw = str(source.get("internshipId") or "").strip()
            if raw.isdigit():
                out.add(int(raw))
    return out


def _binding_subject_allows(binding, user: dict) -> bool:
    subject_type = str(binding.subject_type or "").upper()
    subject_id = str(binding.subject_id or "").strip()
    if subject_type == "USER":
        return bool(subject_id and subject_id == _actor_id(user))
    if subject_type == "STUDENT":
        return bool(subject_id and subject_id in _student_identity_values(user))
    if subject_type == "ROLE":
        role = str((user or {}).get("currentRoleCode") or (user or {}).get("userType") or "").upper()
        return bool(subject_id and subject_id.upper() == role)
    return False


def _internship_scope_allows(db, bindings, user: dict) -> bool:
    ids = _scope_internship_ids(bindings)
    if not ids:
        return False
    try:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        for internship_id in ids:
            try:
                assert_internship_record_scope(db, internship_id, user, "访问实习业务文件")
                return True
            except Exception:
                continue
    except Exception:
        return False
    return False


def authorize_file_object(file_obj, bindings: list[Any], user: dict, action: str = "meta", db=None) -> bool:
    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id or int(file_obj.tenant_id or 0) != tenant_id or file_obj.is_deleted:
        return False
    if action in {"download", "preview", "submit", "archive", "bind"} and not _scan_ready(file_obj):
        return False

    resolver = _RESOLVERS.get(str(file_obj.biz_type or "").upper())
    if resolver is not None:
        try:
            return bool(resolver(db, file_obj, bindings, user or {}, action))
        except Exception:
            return False

    actor = _actor_id(user or {})
    owner = str(file_obj.owner_user_id or file_obj.created_by or "").strip()
    if actor and owner and actor == owner:
        return True

    active = _active_bindings(bindings)
    if any(_binding_subject_allows(item, user or {}) for item in active):
        return True

    if str((user or {}).get("userType") or "").upper() == "STUDENT":
        return False

    return _internship_scope_allows(db, active, user or {})


def _load(db, tenant_id: int, file_id: int):
    file_obj = db.scalar(select(FileObject).where(
        FileObject.id == file_id,
        FileObject.tenant_id == tenant_id,
        FileObject.is_deleted.is_(False),
    ))
    if not file_obj:
        return None, []
    bindings = list(db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == tenant_id,
        FileBinding.file_id == file_id,
        FileBinding.is_deleted.is_(False),
    )).all())
    return file_obj, bindings


def require_file_access(file_id: str, *, user: dict | None = None, action: str = "meta"):
    if not db_enabled() or not str(file_id or "").isdigit():
        raise not_found("文件不存在")
    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id:
        raise not_found("文件不存在")
    actor = user or get_current_user_ctx() or {}
    db = get_sessionmaker()()
    try:
        file_obj, bindings = _load(db, tenant_id, int(file_id))
        if not file_obj or not authorize_file_object(file_obj, bindings, actor, action, db=db):
            raise not_found("文件不存在")
        return file_obj
    finally:
        db.close()


def upsert_file_binding(
    file_id: str,
    *,
    biz_type: str,
    biz_id: str,
    relation_type: str = "ATTACHMENT",
    subject_type: str = "BUSINESS_OBJECT",
    subject_id: str | None = None,
    batch_id: str | None = None,
    version_no: int = 1,
    scope_json: dict | None = None,
    user: dict | None = None,
    db=None,
):
    if not str(file_id or "").isdigit() or not db_enabled():
        return None
    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文", http_status=403)
    own = db is None
    working = db or get_sessionmaker()()
    try:
        file_obj, _ = _load(working, tenant_id, int(file_id))
        if not file_obj or not _scan_ready(file_obj):
            raise not_found("文件不存在")
        normalized_biz = str(biz_type or "").upper()
        normalized_id = str(biz_id or "").strip()
        relation = str(relation_type or "ATTACHMENT").upper()
        if not normalized_biz or not normalized_id:
            raise AppException("VALIDATION_ERROR", "业务文件绑定参数不完整")
        row = working.scalar(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.file_id == int(file_id),
            FileBinding.biz_type == normalized_biz,
            FileBinding.biz_id == normalized_id,
            FileBinding.relation_type == relation,
            FileBinding.is_deleted.is_(False),
        ))
        if row is None:
            actor_id = _actor_id(user or get_current_user_ctx() or {})
            row = FileBinding(
                tenant_id=tenant_id,
                file_id=int(file_id),
                biz_type=normalized_biz,
                biz_id=normalized_id,
                relation_type=relation,
                subject_type=str(subject_type or "BUSINESS_OBJECT").upper(),
                subject_id=str(subject_id).strip() if subject_id not in (None, "") else None,
                batch_id=str(batch_id).strip() if batch_id not in (None, "") else None,
                version_no=max(1, int(version_no or 1)),
                is_current=True,
                status="ACTIVE",
                scope_json=dict(scope_json or {}),
                data_scope_snapshot_json=dict(scope_json or {}),
                created_by=int(actor_id) if actor_id.isdigit() else None,
            )
            working.add(row)
        else:
            row.is_current = True
            row.status = "ACTIVE"
            row.scope_json = dict(scope_json or row.scope_json or {})
            row.data_scope_snapshot_json = dict(scope_json or row.data_scope_snapshot_json or {})
        file_obj.biz_type = normalized_biz
        file_obj.biz_id = normalized_id
        file_obj.visibility = "BIZ_SCOPED"
        if own:
            working.commit()
            working.refresh(row)
        else:
            working.flush()
        return row
    finally:
        if own:
            working.close()


def file_view(file_obj, *, user: dict, bindings: list[Any], db) -> dict:
    scan = str(file_obj.scan_status or "NOT_REQUIRED").upper()
    can_read = authorize_file_object(file_obj, bindings, user, "preview", db=db)
    return {
        "fileId": str(file_obj.id),
        "fileName": file_obj.file_name,
        "ext": file_obj.ext,
        "mimeType": file_obj.mime_type,
        "sizeBytes": file_obj.size_bytes,
        "sha256": file_obj.sha256,
        "bizType": file_obj.biz_type,
        "bizId": file_obj.biz_id,
        "status": file_obj.status,
        "scanStatus": scan,
        "statusText": STATUS_TEXT.get(scan, "状态未知"),
        "readyForBusiness": _scan_ready(file_obj),
        "allowedActions": ["viewMetadata"] + (["preview", "download"] if can_read else []),
    }


def list_business_files(biz_type: str, biz_id: str, *, user: dict | None = None) -> list[dict]:
    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id:
        raise not_found("业务对象不存在")
    actor = user or get_current_user_ctx() or {}
    db = get_sessionmaker()()
    try:
        bindings = list(db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.biz_type == str(biz_type or "").upper(),
            FileBinding.biz_id == str(biz_id or ""),
            FileBinding.status == "ACTIVE",
            FileBinding.is_deleted.is_(False),
        )).all())
        out = []
        for binding in bindings:
            file_obj, all_bindings = _load(db, tenant_id, int(binding.file_id))
            if file_obj and authorize_file_object(file_obj, all_bindings, actor, "meta", db=db):
                out.append(file_view(file_obj, user=actor, bindings=all_bindings, db=db))
        if bindings and not out:
            raise not_found("业务对象不存在")
        return out
    finally:
        db.close()
