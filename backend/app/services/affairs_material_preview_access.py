"""Version-bound preview/download authority for Student Affairs material evidence.

The business resolver deliberately supports historical immutable FileVersion rows while
keeping every byte read behind the existing Student Affairs permission/scope predicates
and File Center object authorization.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.models.file import FileBinding, FileObject, FileVersion
from app.modules.student_affairs.services import affairs_material_center_service as center
from app.services.db_service import _tid, session
from app.services.file_access_service import register_file_resolver, require_file_access
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend
from app.core.redis_client import cache_set_json_if_absent

PREVIEW_TTL_SECONDS = 180
DOWNLOAD_TTL_SECONDS = 60
TICKET_TYPE = "student-affairs-material-ticket"
HISTORICAL_VERSION_STATUS = center.READY_VERSION_STATUS | {"INVALIDATED", "REJECTED"}
BINDING_STATUS = {"ACTIVE", "SUPERSEDED", "ARCHIVED"}


def _actor(user: dict | None) -> str:
    value = resolve_message_user_id(user or {}) or (user or {}).get("userId") or (user or {}).get("sub")
    return str(value or "")


def _action(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in {"preview", "download"}:
        raise AppException("VALIDATION_ERROR", "文件动作仅支持 preview/download")
    return normalized


def _student_self(db, requirement, user: dict) -> bool:
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        return False
    explicit = str((user or {}).get("studentId") or "").strip()
    if explicit.isdigit() and int(explicit) == int(requirement.student_id):
        return True
    student_no = str((user or {}).get("studentNo") or "").strip()
    if not student_no:
        return False
    try:
        from app.models import StudentProfile
        row = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.id == int(requirement.student_id),
            StudentProfile.student_no == student_no,
            StudentProfile.is_deleted.is_(False),
        )).first()
        return row is not None
    except Exception:
        return False


def _requirement_for_binding(db, binding: FileBinding):
    from app.models.affairs_operations import AffairsMaterialRequirement

    raw = str(binding.biz_id or "").strip()
    if not raw.isdigit():
        raise not_found("学工材料不存在")
    requirement = db.scalars(select(AffairsMaterialRequirement).where(
        AffairsMaterialRequirement.id == int(raw),
        AffairsMaterialRequirement.tenant_id == _tid(),
        AffairsMaterialRequirement.is_deleted.is_(False),
    )).first()
    if not requirement:
        raise not_found("学工材料不存在")
    return requirement


@register_file_resolver("MATERIAL_REQUIREMENT")
def affairs_material_file_resolver(db, file_obj, bindings, user: dict, action: str) -> bool:
    """Preserve Student self access and apply the same staff scope as the material center.

    Historical SUPERSEDED bindings remain legitimate read evidence; this resolver does not
    make them current again. Exact FileVersion membership is verified by resolve_material().
    """
    if db is None:
        return False
    valid = [
        binding for binding in bindings
        if not binding.is_deleted
        and str(binding.module_code or "").lower() == center.MODULE_CODE
        and str(binding.relation_type or "").upper() == "MATERIAL_SUBMISSION"
        and str(binding.status or "").upper() in BINDING_STATUS
        and binding.version_id and binding.asset_id
    ]
    requirement_ids = {str(binding.biz_id or "").strip() for binding in valid}
    if len(requirement_ids) != 1:
        return False
    try:
        requirement = _requirement_for_binding(db, valid[0])
        if _student_self(db, requirement, user or {}):
            return True
        return bool(center._staff_can_enumerate(db, requirement, user or {}))
    except Exception:
        return False


def resolve_material(file_id: int, file_version_id: int, user: dict, *, action: str) -> tuple[FileObject, FileVersion, Path]:
    normalized = _action(action)
    target_file_id = int(file_id)
    target_version_id = int(file_version_id)
    with session() as db:
        binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(),
            FileBinding.file_id == target_file_id,
            FileBinding.version_id == target_version_id,
            FileBinding.module_code == center.MODULE_CODE,
            FileBinding.relation_type == "MATERIAL_SUBMISSION",
            FileBinding.status.in_(BINDING_STATUS),
            FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.id.desc())).first()
        if not binding:
            raise not_found("学工材料不存在")

        requirement = _requirement_for_binding(db, binding)
        if not (_student_self(db, requirement, user) or center._staff_can_enumerate(db, requirement, user)):
            raise not_found("学工材料不存在")

        version = db.scalars(select(FileVersion).where(
            FileVersion.id == target_version_id,
            FileVersion.tenant_id == _tid(),
            FileVersion.asset_id == binding.asset_id,
            FileVersion.file_object_id == target_file_id,
            FileVersion.is_deleted.is_(False),
        )).first()
        if not version or str(version.status or "").upper() not in HISTORICAL_VERSION_STATUS:
            raise not_found("学工材料不存在")

        require_file_access(str(target_file_id), user=user, action=normalized)
        file_obj = db.scalars(select(FileObject).where(
            FileObject.id == target_file_id,
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        )).first()
        if not file_obj or not center._file_ready(file_obj):
            raise not_found("学工材料不存在")

        path = get_backend().fetch_local(file_obj.file_key)
        if not path or not path.exists():
            raise not_found("学工材料不存在")
        return file_obj, version, path


def issue_ticket(file_id: int, file_version_id: int, action: str, user: dict) -> dict:
    normalized = _action(action)
    file_obj, version, _ = resolve_material(file_id, file_version_id, user, action=normalized)
    now = int(time.time())
    ttl = PREVIEW_TTL_SECONDS if normalized == "preview" else DOWNLOAD_TTL_SECONDS
    token = jwt.encode({
        "typ": TICKET_TYPE,
        "jti": uuid.uuid4().hex,
        "tenantId": int(_tid()),
        "fileId": int(file_obj.id),
        "fileVersionId": int(version.id),
        "action": normalized,
        "actor": _actor(user),
        "iat": now,
        "exp": now + ttl,
    }, settings.JWT_SECRET, algorithm=settings.JWT_ALG)
    return {
        "ticket": token,
        "action": normalized,
        "fileId": str(file_obj.id),
        "fileVersionId": str(version.id),
        "versionNo": int(version.version_no or 0),
        "expiresIn": ttl,
        "singleUse": normalized == "download",
        "url": f"/api/v1/student-affairs/material-center/files/{int(file_obj.id)}/{normalized}?ticket={token}",
    }


def consume_ticket(file_id: int, action: str, ticket: str, user: dict) -> tuple[Path, str, int]:
    normalized = _action(action)
    try:
        payload = jwt.decode(str(ticket or ""), settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except Exception:
        raise not_found("学工材料不存在")
    version_id = int(payload.get("fileVersionId") or 0)
    if (
        payload.get("typ") != TICKET_TYPE
        or int(payload.get("tenantId") or 0) != int(_tid())
        or int(payload.get("fileId") or 0) != int(file_id)
        or version_id <= 0
        or str(payload.get("action") or "") != normalized
        or str(payload.get("actor") or "") != _actor(user)
    ):
        raise not_found("学工材料不存在")

    file_obj, version, path = resolve_material(int(file_id), version_id, user, action=normalized)
    if normalized == "download":
        ttl = max(1, int(payload.get("exp") or 0) - int(time.time()))
        acquired = cache_set_json_if_absent(
            f"student-affairs-material-ticket:used:{_tid()}:{payload.get('jti')}",
            {"usedAt": int(time.time()), "actor": _actor(user), "fileId": int(file_id), "fileVersionId": version_id},
            ttl,
        )
        if acquired is False:
            raise not_found("下载票据不存在或已失效")
        if acquired is None:
            raise AppException("TICKET_STORE_UNAVAILABLE", "下载票据存储不可用，请稍后重试", http_status=503)
    return path, file_obj.file_name, int(version.id)


__all__ = ["affairs_material_file_resolver", "consume_ticket", "issue_ticket", "resolve_material"]
