"""Graduation material access resolver and terminal ticket enforcement."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import jwt
from sqlalchemy import func, select

from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.core.redis_client import cache_set_json_if_absent
from app.models import GraduationStudent
from app.models.data_exchange import ExportJob
from app.models.file import FileBinding, FileObject
from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid, session
from app.services.file_access_service import require_file_access
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

from .definitions import MODULE_CODE


PREVIEW_TTL_SECONDS = 180
DOWNLOAD_TTL_SECONDS = 60


def _tenant() -> int:
    try:
        value = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        value = 0
    if not value:
        raise not_found("毕业设计材料不存在")
    return value


def _actor(user: dict) -> str:
    return str(resolve_message_user_id(user or {}) or (user or {}).get("userId") or (user or {}).get("sub") or "")


def _binding_student_id(bindings: list[FileBinding]) -> int:
    ids: set[int] = set()
    for binding in bindings:
        raw = (binding.scope_json or {}).get("gdStudentId")
        try:
            if raw not in (None, ""):
                ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    if len(ids) != 1:
        raise not_found("毕业设计材料不存在")
    return next(iter(ids))


def resolve_material(file_id: int, user: dict, *, action: str) -> tuple[FileObject, Path]:
    """Binding -> public resolver -> graduation scope -> file state -> bytes."""
    normalized = str(action or "").lower()
    if normalized not in {"preview", "download"}:
        raise AppException("VALIDATION_ERROR", "文件动作仅支持 preview/download")
    with session() as db:
        bindings = list(db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.file_id == int(file_id),
            FileBinding.module_code == MODULE_CODE, FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.is_current.desc(), FileBinding.id.desc())).all())
        if not bindings:
            raise not_found("毕业设计材料不存在")
        gd_student_id = _binding_student_id(bindings)
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == gd_student_id,
            GraduationStudent.is_deleted.is_(False),
        )).first()
        if not student:
            raise not_found("毕业设计材料不存在")
        if str((user or {}).get("userType") or "").upper() == "STUDENT":
            current = resolve_current_gd_student(db, user)
            if not current or int(current.id) != int(student.id):
                raise not_found("毕业设计材料不存在")
        else:
            assert_student_access(db, student, f"material.{normalized}")
        # The public center remains the object-level authorization authority.
        require_file_access(str(file_id), user=user, action=normalized)
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(), FileObject.id == int(file_id),
            FileObject.is_deleted.is_(False),
        )).first()
        if not file_obj:
            raise not_found("毕业设计材料不存在")
        scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
        if not is_downloadable_status(file_obj.status) or scan not in READY_SCAN_STATES:
            raise not_found("毕业设计材料不存在")
        path = get_backend().fetch_local(file_obj.file_key)
        if not path or not path.exists():
            raise not_found("毕业设计材料不存在")
        return file_obj, path


def issue_ticket(file_id: int, action: str, user: dict) -> dict:
    normalized = str(action or "").lower()
    if normalized not in {"preview", "download"}:
        raise AppException("VALIDATION_ERROR", "票据动作仅支持 preview/download")
    resolve_material(int(file_id), user, action=normalized)
    now = int(time.time())
    ttl = PREVIEW_TTL_SECONDS if normalized == "preview" else DOWNLOAD_TTL_SECONDS
    jti = uuid.uuid4().hex
    token = jwt.encode({
        "typ": "gd-material-ticket", "jti": jti,
        "tenantId": _tenant(), "fileId": int(file_id), "action": normalized,
        "actor": _actor(user), "iat": now, "exp": now + ttl,
    }, settings.JWT_SECRET, algorithm=settings.JWT_ALG)
    mobile = str((user or {}).get("userType") or "").upper() == "STUDENT"
    prefix = "/api/v1/mobile/graduation" if mobile else "/api/v1/graduation"
    return {
        "ticket": token, "action": normalized, "expiresIn": ttl,
        "singleUse": normalized == "download",
        "url": f"{prefix}/material-center/files/{int(file_id)}/{normalized}?ticket={token}",
    }


def resolve_package(file_id: int, user: dict) -> tuple[FileObject, Path]:
    """Resolve an active ExportJob package without scanning business records."""
    with session() as db:
        job = db.scalars(select(ExportJob).where(
            ExportJob.tenant_id == _tid(), ExportJob.module_code == MODULE_CODE,
            ExportJob.adapter_type == "GRADUATION_ARCHIVE",
            ExportJob.file_object_id == int(file_id), ExportJob.status == "SUCCEEDED",
            ExportJob.revoked_at.is_(None), ExportJob.is_deleted.is_(False),
        ).order_by(ExportJob.id.desc())).first()
        if not job or (job.expires_at and job.expires_at.timestamp() <= time.time()):
            raise not_found("毕业设计归档包不存在")
        snapshot = dict(job.filter_snapshot_json or {})
        if str((user or {}).get("userType") or "").upper() == "STUDENT":
            student = resolve_current_gd_student(db, user)
            if not student or snapshot.get("scopeType") != "STUDENT" or str(snapshot.get("scopeValue")) != str(student.id):
                raise not_found("毕业设计归档包不存在")
        else:
            from .query_service import student_scope_predicate

            scope_stmt = select(func.count()).select_from(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(),
                GraduationStudent.batch_id == int(snapshot.get("batchId") or 0),
                GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
            )
            kind = str(snapshot.get("scopeType") or "BATCH").upper()
            value = str(snapshot.get("scopeValue") or "")
            if kind == "STUDENT" and value.isdigit():
                scope_stmt = scope_stmt.where(GraduationStudent.id == int(value))
            elif kind == "CLASS":
                scope_stmt = scope_stmt.where(GraduationStudent.class_id == value)
            elif kind == "MAJOR":
                scope_stmt = scope_stmt.where(GraduationStudent.major_id == value)
            elif kind == "COLLEGE":
                scope_stmt = scope_stmt.where(GraduationStudent.college_id == value)
            total = int(db.scalar(scope_stmt) or 0)
            allowed = int(db.scalar(scope_stmt.where(student_scope_predicate(user))) or 0)
            if not total or allowed != total:
                raise not_found("毕业设计归档包不存在")
        require_file_access(str(file_id), user=user, action="download")
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(), FileObject.id == int(file_id),
            FileObject.is_deleted.is_(False),
        )).first()
        if not file_obj:
            raise not_found("毕业设计归档包不存在")
        scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
        if not is_downloadable_status(file_obj.status) or scan not in READY_SCAN_STATES:
            raise not_found("毕业设计归档包不存在")
        path = get_backend().fetch_local(file_obj.file_key)
        if not path or not path.exists():
            raise not_found("毕业设计归档包不存在")
        return file_obj, path


def issue_package_ticket(file_id: int, user: dict) -> dict:
    resolve_package(int(file_id), user)
    now = int(time.time())
    token = jwt.encode({
        "typ": "gd-package-ticket", "jti": uuid.uuid4().hex,
        "tenantId": _tenant(), "fileId": int(file_id), "action": "download",
        "actor": _actor(user), "iat": now, "exp": now + DOWNLOAD_TTL_SECONDS,
    }, settings.JWT_SECRET, algorithm=settings.JWT_ALG)
    mobile = str((user or {}).get("userType") or "").upper() == "STUDENT"
    prefix = "/api/v1/mobile/graduation" if mobile else "/api/v1/graduation"
    return {"ticket": token, "action": "download", "expiresIn": DOWNLOAD_TTL_SECONDS,
            "singleUse": True,
            "url": f"{prefix}/material-center/packages/{int(file_id)}/download?ticket={token}"}


def consume_package_ticket(file_id: int, ticket: str, user: dict) -> tuple[Path, str]:
    try:
        payload = jwt.decode(str(ticket or ""), settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except Exception:
        raise not_found("毕业设计归档包不存在")
    if (
        payload.get("typ") != "gd-package-ticket"
        or int(payload.get("tenantId") or 0) != _tenant()
        or int(payload.get("fileId") or 0) != int(file_id)
        or str(payload.get("actor") or "") != _actor(user)
    ):
        raise not_found("毕业设计归档包不存在")
    file_obj, path = resolve_package(int(file_id), user)
    ttl = max(1, int(payload.get("exp") or 0) - int(time.time()))
    acquired = cache_set_json_if_absent(
        f"gd-package-ticket:used:{_tenant()}:{payload.get('jti')}",
        {"usedAt": int(time.time()), "actor": _actor(user), "fileId": int(file_id)}, ttl,
    )
    if acquired is False:
        raise not_found("下载票据不存在或已失效")
    if acquired is None:
        raise AppException("TICKET_STORE_UNAVAILABLE", "下载票据存储不可用，请稍后重试", http_status=503)
    return path, file_obj.file_name


def consume_ticket(file_id: int, action: str, ticket: str, user: dict) -> tuple[Path, str]:
    try:
        payload = jwt.decode(str(ticket or ""), settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except Exception:
        raise not_found("毕业设计材料不存在")
    normalized = str(action or "").lower()
    if (
        payload.get("typ") != "gd-material-ticket"
        or int(payload.get("tenantId") or 0) != _tenant()
        or int(payload.get("fileId") or 0) != int(file_id)
        or payload.get("action") != normalized
        or str(payload.get("actor") or "") != _actor(user)
    ):
        raise not_found("毕业设计材料不存在")
    file_obj, path = resolve_material(int(file_id), user, action=normalized)
    if normalized == "download":
        ttl = max(1, int(payload.get("exp") or 0) - int(time.time()))
        acquired = cache_set_json_if_absent(
            f"gd-material-ticket:used:{_tenant()}:{payload.get('jti')}",
            {"usedAt": int(time.time()), "actor": _actor(user), "fileId": int(file_id)},
            ttl,
        )
        if acquired is False:
            raise not_found("下载票据不存在或已失效")
        if acquired is None:
            raise AppException(
                "TICKET_STORE_UNAVAILABLE", "下载票据存储不可用，请稍后重试", http_status=503,
            )
    return path, file_obj.file_name


__all__ = [
    "consume_package_ticket", "consume_ticket", "issue_package_ticket", "issue_ticket",
    "resolve_material", "resolve_package",
]
