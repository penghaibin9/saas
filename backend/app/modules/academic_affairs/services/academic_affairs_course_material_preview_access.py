"""Course-scoped preview/download authority for academic course materials.

Course material rows are the business relation: legacy/new uploads may be TEMP_PRIVATE and may not
have a generic FileBinding.  The Reader therefore validates the caller against the course first,
then resolves exactly the file_id attached to an ACTIVE AaCourseMaterial row.  It never widens that
relationship into a generic File Center URL.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.core.redis_client import cache_set_json_if_absent
from app.models import AaCourseMaterial
from app.models.file import FileObject
from app.modules.academic_affairs.services import academic_affairs_course_public_service as course_svc
from app.services.db_service import _tid, session
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

PREVIEW_TTL_SECONDS = 180
DOWNLOAD_TTL_SECONDS = 60
TICKET_TYPE = "academic-course-material-ticket"

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
        raise AppException("VALIDATION_ERROR", "课程材料动作仅支持 preview/download")
    return value


def _file_ready(file_obj: FileObject | None) -> bool:
    if not file_obj:
        return False
    scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
    return bool(is_downloadable_status(file_obj.status) and scan in READY_SCAN_STATES)


def _course_scope(course_id: int, user: dict) -> None:
    # Canonical course service owns tenant/college data-scope semantics.  A successful read is the
    # prerequisite for every Reader operation; browser-side possession of materialId/fileId is not.
    course_svc.get_course(int(course_id), user)


def _material_row(db, course_id: int, material_id: int) -> AaCourseMaterial:
    row = db.scalars(select(AaCourseMaterial).where(
        AaCourseMaterial.id == int(material_id),
        AaCourseMaterial.course_id == int(course_id),
        AaCourseMaterial.tenant_id == _tid(),
        AaCourseMaterial.status == "ACTIVE",
        AaCourseMaterial.is_deleted.is_(False),
    )).first()
    if not row or not row.file_id:
        raise not_found("课程材料附件不存在")
    return row


def _file_object(db, file_id: int) -> FileObject:
    row = db.scalars(select(FileObject).where(
        FileObject.id == int(file_id),
        FileObject.tenant_id == _tid(),
        FileObject.is_deleted.is_(False),
    )).first()
    if not _file_ready(row):
        raise not_found("课程材料附件不存在")
    return row


def list_reader_files(course_id: int, user: dict) -> list[dict]:
    _course_scope(int(course_id), user)
    with session() as db:
        materials = db.scalars(select(AaCourseMaterial).where(
            AaCourseMaterial.course_id == int(course_id),
            AaCourseMaterial.tenant_id == _tid(),
            AaCourseMaterial.status == "ACTIVE",
            AaCourseMaterial.is_deleted.is_(False),
            AaCourseMaterial.file_id.is_not(None),
        ).order_by(AaCourseMaterial.created_at.desc(), AaCourseMaterial.id.desc())).all()
        file_ids = {int(item.file_id) for item in materials if item.file_id}
        files = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.id.in_(file_ids),
            FileObject.is_deleted.is_(False),
        )).all() if file_ids else []
        file_by_id = {int(item.id): item for item in files}

        rows = []
        for material in materials:
            file_obj = file_by_id.get(int(material.file_id))
            scan = str(getattr(file_obj, "scan_status", None) or SCAN_NOT_REQUIRED).upper()
            ready = _file_ready(file_obj)
            rows.append({
                "materialId": str(material.id),
                "materialType": material.material_type,
                "title": material.title,
                "remark": material.remark,
                "uploader": material.uploader,
                "createdAt": material.created_at.isoformat(timespec="seconds") if material.created_at else None,
                "fileId": str(material.file_id),
                "fileName": material.file_name or (file_obj.file_name if file_obj else None) or material.title,
                "ext": (file_obj.ext if file_obj else None) or "",
                "mimeType": (file_obj.mime_type if file_obj else None) or "",
                "sizeBytes": int(file_obj.size_bytes or 0) if file_obj else 0,
                "scanStatus": scan,
                "statusText": STATUS_TEXT.get(scan, "状态未知") if file_obj else "附件不存在",
                "readyForBusiness": ready,
                "allowedActions": ["viewMetadata", "preview", "download"] if ready else ["viewMetadata"],
                "sourceSha256": (file_obj.sha256 if file_obj else None) or "",
            })
        return rows


def resolve_material(course_id: int, material_id: int, user: dict, *, action: str) -> tuple[FileObject, Path]:
    _normalized_action(action)
    _course_scope(int(course_id), user)
    with session() as db:
        material = _material_row(db, int(course_id), int(material_id))
        file_obj = _file_object(db, int(material.file_id))
        path = get_backend().fetch_local(file_obj.file_key)
        if not path or not path.exists():
            raise not_found("课程材料附件不存在")
        return file_obj, path


def issue_ticket(course_id: int, material_id: int, action: str, user: dict) -> dict:
    normalized = _normalized_action(action)
    file_obj, _ = resolve_material(int(course_id), int(material_id), user, action=normalized)
    now = int(time.time())
    ttl = PREVIEW_TTL_SECONDS if normalized == "preview" else DOWNLOAD_TTL_SECONDS
    token = jwt.encode({
        "typ": TICKET_TYPE,
        "jti": uuid.uuid4().hex,
        "tenantId": int(_tid()),
        "courseId": int(course_id),
        "materialId": int(material_id),
        "fileId": int(file_obj.id),
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
        "businessTicket": True,
        "url": f"/api/v1/academic-affairs/courses/{int(course_id)}/materials/{int(material_id)}/{normalized}?ticket={token}",
    }


def consume_ticket(course_id: int, material_id: int, action: str, ticket: str, user: dict) -> tuple[Path, str, str | None]:
    normalized = _normalized_action(action)
    try:
        payload = jwt.decode(str(ticket or ""), settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except Exception:
        raise not_found("课程材料附件不存在")
    if (
        payload.get("typ") != TICKET_TYPE
        or int(payload.get("tenantId") or 0) != int(_tid())
        or int(payload.get("courseId") or 0) != int(course_id)
        or int(payload.get("materialId") or 0) != int(material_id)
        or str(payload.get("action") or "") != normalized
        or str(payload.get("actor") or "") != _actor(user)
    ):
        raise not_found("课程材料附件不存在")

    file_obj, path = resolve_material(int(course_id), int(material_id), user, action=normalized)
    if int(payload.get("fileId") or 0) != int(file_obj.id):
        raise not_found("课程材料附件不存在")
    if normalized == "download":
        ttl = max(1, int(payload.get("exp") or 0) - int(time.time()))
        acquired = cache_set_json_if_absent(
            f"academic-course-material-ticket:used:{_tid()}:{payload.get('jti')}",
            {
                "usedAt": int(time.time()),
                "actor": _actor(user),
                "courseId": int(course_id),
                "materialId": int(material_id),
                "fileId": int(file_obj.id),
            },
            ttl,
        )
        if acquired is False:
            raise not_found("下载票据不存在或已失效")
        if acquired is None:
            raise AppException("TICKET_STORE_UNAVAILABLE", "下载票据存储不可用，请稍后重试", http_status=503)
    return path, file_obj.file_name, file_obj.mime_type


__all__ = ["consume_ticket", "issue_ticket", "list_reader_files", "resolve_material"]
