"""Task-scoped preview/download authority for versioned internship materials."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.core.redis_client import cache_set_json_if_absent
from app.models.file import FileBinding, FileObject, FileVersion
from app.modules.internship.services import internship_material_center_service as material_center
from app.services.db_service import _tid, session
from app.services.file_access_service import require_file_access
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

PREVIEW_TTL_SECONDS = 180
DOWNLOAD_TTL_SECONDS = 60
TICKET_TYPE = "internship-material-ticket"


def _actor(user: dict | None) -> str:
    value = resolve_message_user_id(user or {}) or (user or {}).get("userId") or (user or {}).get("sub")
    return str(value or "")


def _normalized_action(action: str) -> str:
    value = str(action or "").strip().lower()
    if value not in {"preview", "download"}:
        raise AppException("VALIDATION_ERROR", "文件动作仅支持 preview/download")
    return value


def _binding_scope(binding: FileBinding) -> dict:
    return dict(binding.data_scope_snapshot_json or binding.scope_json or {})


def resolve_material(file_id: int, user: dict, *, action: str) -> tuple[FileObject, Path]:
    """Resolve only the current internship material binding the caller can actually access."""
    normalized = _normalized_action(action)
    target_file_id = int(file_id)
    with session() as db:
        binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(),
            FileBinding.file_id == target_file_id,
            FileBinding.module_code == material_center.MODULE_CODE,
            FileBinding.relation_type == "MATERIAL",
            FileBinding.is_current.is_(True),
            FileBinding.status == "ACTIVE",
            FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.id.desc())).first()
        if not binding:
            raise not_found("实习材料不存在")

        scope = _binding_scope(binding)
        internship_id = str(scope.get("internshipId") or "").strip()
        if not internship_id.isdigit():
            raise not_found("实习材料不存在")
        material_center._assert_scope(db, int(internship_id), user, f"material.{normalized}")

        version = db.scalars(select(FileVersion).where(
            FileVersion.id == binding.version_id,
            FileVersion.tenant_id == _tid(),
            FileVersion.file_object_id == target_file_id,
            FileVersion.asset_id == binding.asset_id,
            FileVersion.is_current.is_(True),
            FileVersion.is_deleted.is_(False),
        )).first()
        if not version or version.status not in material_center.READY_VERSION_STATUS:
            raise not_found("实习材料不存在")

        require_file_access(str(target_file_id), user=user, action=normalized)
        file_obj = db.scalars(select(FileObject).where(
            FileObject.id == target_file_id,
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        )).first()
        if not material_center._file_ready(file_obj):
            raise not_found("实习材料不存在")

        path = get_backend().fetch_local(file_obj.file_key)
        if not path or not path.exists():
            raise not_found("实习材料不存在")
        return file_obj, path


def issue_ticket(file_id: int, action: str, user: dict) -> dict:
    normalized = _normalized_action(action)
    resolve_material(int(file_id), user, action=normalized)
    now = int(time.time())
    ttl = PREVIEW_TTL_SECONDS if normalized == "preview" else DOWNLOAD_TTL_SECONDS
    token = jwt.encode({
        "typ": TICKET_TYPE,
        "jti": uuid.uuid4().hex,
        "tenantId": int(_tid()),
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
        "url": f"/api/v1/internship/material-center/files/{int(file_id)}/{normalized}?ticket={token}",
    }


def consume_ticket(file_id: int, action: str, ticket: str, user: dict) -> tuple[Path, str]:
    normalized = _normalized_action(action)
    try:
        payload = jwt.decode(str(ticket or ""), settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except Exception:
        raise not_found("实习材料不存在")
    if (
        payload.get("typ") != TICKET_TYPE
        or int(payload.get("tenantId") or 0) != int(_tid())
        or int(payload.get("fileId") or 0) != int(file_id)
        or str(payload.get("action") or "") != normalized
        or str(payload.get("actor") or "") != _actor(user)
    ):
        raise not_found("实习材料不存在")

    file_obj, path = resolve_material(int(file_id), user, action=normalized)
    if normalized == "download":
        ttl = max(1, int(payload.get("exp") or 0) - int(time.time()))
        acquired = cache_set_json_if_absent(
            f"internship-material-ticket:used:{_tid()}:{payload.get('jti')}",
            {"usedAt": int(time.time()), "actor": _actor(user), "fileId": int(file_id)},
            ttl,
        )
        if acquired is False:
            raise not_found("下载票据不存在或已失效")
        if acquired is None:
            raise AppException("TICKET_STORE_UNAVAILABLE", "下载票据存储不可用，请稍后重试", http_status=503)
    return path, file_obj.file_name


__all__ = ["consume_ticket", "issue_ticket", "resolve_material"]
