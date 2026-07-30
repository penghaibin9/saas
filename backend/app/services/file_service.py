"""统一文件服务：流式上传、resolver 对象授权、扫描隔离和业务绑定。"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.permissions import has_permission, is_super_admin
from app.db.session import db_enabled, get_sessionmaker
from app.services.file_content_security import (
    FILE_STATUS_AVAILABLE,
    FILE_STATUS_QUARANTINED,
    is_downloadable_status,
    is_scan_required_for_upload,
    sanitize_filename,
    validate_content,
    validate_content_path,
)
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED, SCAN_PENDING
from app.services.storage import get_backend

ALLOWED_EXT = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "png", "jpg", "jpeg", "gif", "zip", "txt", "csv",
}
BLOCKED_EXT = {"exe", "js", "bat", "sh", "php", "jsp", "html", "svg"}
MAX_SIZE = 50 * 1024 * 1024

_MEM_REGISTRY: dict[str, dict] = {}
_MEM_TENANT: dict[str, int] = {}
_MEM_OWNER: dict[str, int] = {}
_MEM_META_EXTRA: dict[str, dict] = {}

# 仅用于 DB 关闭的兼容内存模式；真实 DB 模式全部委托 resolver registry。
_MEMORY_BIZ_VIEW_PERM: dict[str, str] = {
    "DISCIPLINE": "studentAffairs.discipline.view",
    "DISCIPLINE_APPEAL": "studentAffairs.discipline.view",
    "LEAGUE": "studentAffairs.league.view",
    "CLUB": "studentAffairs.club.view",
    "FUNDING": "studentAffairs.funding.view",
    "REDUCTION": "studentAffairs.funding.view",
    "LOAN": "studentAffairs.funding.view",
    "HOME_SCHOOL": "studentAffairs.homeSchool.view",
    "LEAVE": "studentAffairs.leave.view",
    "AID": "studentAffairs.aid.view",
    "RISK": "studentAffairs.risk.view",
    "MENTAL": "studentAffairs.risk.view",
    "GRADUATION_MATERIAL": "graduationDesign.view",
    "INTERNSHIP": "internship.student.material.view",
    "COURSE_MATERIAL": "academicAffairs.course.view",
    "ATTACHMENT": "studentAffairs.student.view",
}


def upload_dir() -> Path:
    directory = Path(settings.UPLOAD_DIR or "./uploads")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def validate_ext(filename: str) -> str:
    safe = sanitize_filename(filename)
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    if ext in BLOCKED_EXT or ext not in ALLOWED_EXT:
        raise AppException(
            "FILE_TYPE_NOT_ALLOWED",
            f"文件类型不允许：.{ext or '未知'}",
            details={"allowed": sorted(ALLOWED_EXT)},
        )
    return ext


def _require_tenant_id() -> int:
    try:
        tenant_id = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tenant_id = 0
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝写入文件")
    return tenant_id


def _actor_user_id(user: dict | None = None) -> int | None:
    from app.services.message_identity import resolve_message_user_id

    return resolve_message_user_id(user or get_current_user_ctx() or {}) or None


def _actor_binding_subject(user: dict) -> tuple[str, str | None]:
    if str(user.get("userType") or "").upper() == "STUDENT":
        value = user.get("studentId") or user.get("studentNo")
        return "STUDENT", str(value).strip() if value not in (None, "") else None
    value = user.get("userId") or user.get("id")
    return "USER", str(value).strip() if value not in (None, "") else None


def _ready(row) -> bool:
    scan_status = str(getattr(row, "scan_status", None) or SCAN_NOT_REQUIRED).upper()
    return bool(
        is_downloadable_status(getattr(row, "status", None))
        and scan_status in READY_SCAN_STATES
    )


def _row_meta(row) -> dict:
    return {
        "fileId": str(row.id),
        "fileName": row.file_name,
        "ext": row.ext,
        "mimeType": row.mime_type,
        "sizeBytes": row.size_bytes,
        "sha256": row.sha256,
        "fileKey": row.file_key,
        "bizType": row.biz_type,
        "bizId": row.biz_id,
        "ownerUserId": row.owner_user_id,
        "visibility": row.visibility,
        "securityLevel": row.security_level,
        "status": row.status,
        "scanRequired": bool(getattr(row, "scan_required", False)),
        "scanStatus": getattr(row, "scan_status", SCAN_NOT_REQUIRED) or SCAN_NOT_REQUIRED,
        "scanAttempts": int(getattr(row, "scan_attempts", 0) or 0),
        "readyForBusiness": _ready(row),
        "storedAt": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
        "createdBy": row.created_by,
    }


def _memory_authorized(user: dict, file_obj, action: str) -> bool:
    try:
        tenant_id = int(current_tenant_id() or 0)
        file_tenant_id = int(getattr(file_obj, "tenant_id", 0) or 0)
    except (TypeError, ValueError):
        return False
    if (
        not tenant_id
        or tenant_id != file_tenant_id
        or getattr(file_obj, "is_deleted", False)
    ):
        return False
    if action in {"download", "preview", "bind", "submit", "archive"} and not _ready(file_obj):
        return False
    if is_super_admin(user) or has_permission(user, "systemAdmin.file.manage"):
        return True
    uid = _actor_user_id(user)
    owner = getattr(file_obj, "owner_user_id", None) or getattr(file_obj, "created_by", None)
    if uid and owner and int(uid) == int(owner):
        return True
    biz_id = str(getattr(file_obj, "biz_id", None) or "").strip()
    if str(user.get("userType") or "").upper() == "STUDENT":
        student_values = {
            str(user.get("studentId") or "").strip(),
            str(user.get("studentNo") or "").strip(),
        }
        return bool(biz_id and biz_id in student_values)
    permission = _MEMORY_BIZ_VIEW_PERM.get(str(getattr(file_obj, "biz_type", "") or "").upper())
    return bool(permission and has_permission(user, permission))


def authorize_file_access(user: dict, file_obj, action: str = "download") -> bool:
    """唯一兼容授权入口。

    DB 模式必须调用阶段 2 resolver registry；内存模式仅为测试/本地兼容保留最小规则。
    """
    if file_obj is None:
        return False
    file_id = str(getattr(file_obj, "id", "") or "")
    if not db_enabled() or not file_id.isdigit():
        return _memory_authorized(user or {}, file_obj, action)

    from app.models.file import FileBinding
    from app.services import file_access_resolvers as _file_access_resolvers  # noqa: F401
    from app.services.file_access_service import authorize_file_object

    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id:
        return False
    db = get_sessionmaker()()
    try:
        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.file_id == int(file_id),
            FileBinding.is_deleted.is_(False),
        )).all()
        return authorize_file_object(
            file_obj,
            list(bindings),
            user or {},
            action,
            db=db,
        )
    except Exception:
        # 鉴权链异常默认拒绝，不能回落到更宽的历史规则。
        return False
    finally:
        db.close()


def _load_file_row(file_id: str):
    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id or not db_enabled() or not str(file_id).isdigit():
        return None
    from app.models.file import FileObject

    db = get_sessionmaker()()
    try:
        return db.scalars(select(FileObject).where(
            FileObject.id == int(file_id),
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
        )).first()
    finally:
        db.close()


def _register_binding(
    file_id: str,
    *,
    biz_type: str,
    biz_id: str | None,
    actor: dict,
    db=None,
) -> None:
    if not biz_id or not str(file_id).isdigit() or not db_enabled():
        return
    from app.services.file_access_service import upsert_file_binding

    subject_type, subject_id = _actor_binding_subject(actor)
    upsert_file_binding(
        file_id,
        biz_type=str(biz_type or "ATTACHMENT").upper(),
        biz_id=str(biz_id),
        subject_type=subject_type,
        subject_id=subject_id,
        user=actor,
        db=db,
    )


async def store_upload(
    file,
    biz_type: str = "ATTACHMENT",
    *,
    biz_id: str | None = None,
    user: dict | None = None,
    visibility: str = "BIZ_SCOPED",
    security_level: str = "NORMAL",
) -> dict:
    """流式落盘并登记。高风险文件进入隔离区，由独立 ClamAV worker 扫描。"""
    filename = sanitize_filename(file.filename or "unnamed")
    _ensure_upload_allowed()
    tenant_id = _require_tenant_id()
    ext = validate_ext(filename)
    max_size = _upload_max_size()
    actor = user or get_current_user_ctx() or {}
    owner_id = _actor_user_id(actor)
    digest = hashlib.sha256()
    size = 0
    key = f"{datetime.now():%Y%m%d}/{uuid.uuid4().hex}.{ext}"
    backend = get_backend()
    target = backend.staging_path(key)
    try:
        with target.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_size:
                    raise AppException(
                        "FILE_TOO_LARGE",
                        f"文件超过 {max_size // (1024 * 1024)}MB 上限（平台规则中心配置）",
                    )
                digest.update(chunk)
                output.write(chunk)
        mime, initial_status = validate_content_path(
            filename=filename,
            declared_content_type=getattr(file, "content_type", None),
            path=target,
            ext=ext,
            biz_type=biz_type,
            source="USER",
        )
        backend.persist(key, target)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    scan_required = is_scan_required_for_upload(ext)
    scan_status = SCAN_PENDING if scan_required else SCAN_NOT_REQUIRED
    status = FILE_STATUS_QUARANTINED if scan_required else initial_status
    now = datetime.utcnow()
    meta = {
        "fileName": filename,
        "ext": ext,
        "sizeBytes": size,
        "sha256": digest.hexdigest(),
        "fileKey": key,
        "bizType": biz_type,
        "bizId": biz_id,
        "visibility": visibility,
        "securityLevel": security_level,
        "mimeType": mime,
        "status": status,
        "scanRequired": scan_required,
        "scanStatus": scan_status,
        "readyForBusiness": not scan_required and status == FILE_STATUS_AVAILABLE,
        "storedAt": now.isoformat(timespec="seconds"),
    }
    if db_enabled():
        from app.models.file import FileObject, FileUploadSession
        from app.services.file_scan_service import enqueue_file_scan

        db = get_sessionmaker()()
        try:
            row = FileObject(
                tenant_id=tenant_id,
                file_key=key,
                file_name=filename,
                ext=ext,
                mime_type=mime,
                size_bytes=size,
                sha256=digest.hexdigest(),
                biz_type=(biz_type or "ATTACHMENT").upper(),
                biz_id=biz_id,
                owner_user_id=owner_id,
                created_by=owner_id,
                visibility=visibility or "BIZ_SCOPED",
                security_level=security_level or "NORMAL",
                status=status,
                storage_backend=str(settings.FILE_STORAGE_BACKEND or "local").lower(),
                storage_zone="QUARANTINE" if scan_required else "ACTIVE",
                upload_source="USER",
                scan_required=scan_required,
                scan_status=scan_status,
                scan_attempts=0,
                available_at=None if scan_required else now,
            )
            db.add(row)
            db.flush()
            db.add(FileUploadSession(
                tenant_id=tenant_id,
                session_key=uuid.uuid4().hex,
                file_id=row.id,
                status="COMPLETED",
                source="LEGACY_API",
                file_name=filename,
                expected_size=size,
                received_size=size,
                completed_at=now,
                created_by=owner_id,
                metadata_json={"bizType": biz_type, "bizId": biz_id},
            ))
            if scan_required:
                enqueue_file_scan(db, row)
            _register_binding(
                str(row.id),
                biz_type=row.biz_type or "ATTACHMENT",
                biz_id=biz_id,
                actor=actor,
                db=db,
            )
            db.commit()
            db.refresh(row)
            meta.update(_row_meta(row))
        finally:
            db.close()
    else:
        file_id = f"mem-{uuid.uuid4().hex[:12]}"
        meta["fileId"] = file_id
        _MEM_REGISTRY[file_id] = dict(meta)
        _MEM_TENANT[file_id] = tenant_id
        _MEM_OWNER[file_id] = owner_id or 0
        _MEM_META_EXTRA[file_id] = {
            "tenant_id": tenant_id,
            "owner_user_id": owner_id,
            "created_by": owner_id,
            "biz_type": biz_type,
            "biz_id": biz_id,
            "visibility": visibility,
            "security_level": security_level,
            "file_key": key,
            "file_name": filename,
            "status": status,
            "scan_status": scan_status,
            "scan_required": scan_required,
            "is_deleted": False,
        }
    return meta


def store_bytes(
    data: bytes,
    filename: str,
    biz_type: str = "ATTACHMENT",
    mime_type: str | None = None,
    *,
    biz_id: str | None = None,
    user: dict | None = None,
    visibility: str = "PRIVATE",
    security_level: str = "NORMAL",
) -> dict:
    """系统生成文件可信写入；仍做结构校验，但不进入用户上传杀毒队列。"""
    tenant_id = _require_tenant_id()
    filename = sanitize_filename(filename)
    ext = validate_ext(filename)
    detected_mime, status = validate_content(
        filename=filename,
        declared_content_type=mime_type,
        data=data,
        ext=ext,
        biz_type=biz_type,
        source="SYSTEM",
    )
    key = f"{datetime.now():%Y%m%d}/{uuid.uuid4().hex}.{ext}"
    backend = get_backend()
    target = backend.staging_path(key)
    target.write_bytes(data)
    backend.persist(key, target)
    now = datetime.utcnow()
    actor = user or get_current_user_ctx() or {}
    owner_id = _actor_user_id(actor)
    meta = {
        "fileName": filename,
        "ext": ext,
        "sizeBytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "fileKey": key,
        "bizType": biz_type,
        "bizId": biz_id,
        "mimeType": detected_mime,
        "status": status,
        "scanRequired": False,
        "scanStatus": SCAN_NOT_REQUIRED,
        "readyForBusiness": True,
        "storedAt": now.isoformat(timespec="seconds"),
    }
    if db_enabled():
        from app.models.file import FileObject

        db = get_sessionmaker()()
        try:
            row = FileObject(
                tenant_id=tenant_id,
                file_key=key,
                file_name=filename,
                ext=ext,
                mime_type=detected_mime,
                size_bytes=len(data),
                sha256=meta["sha256"],
                biz_type=biz_type,
                biz_id=biz_id,
                owner_user_id=owner_id,
                created_by=owner_id,
                visibility=visibility or "PRIVATE",
                security_level=security_level or "NORMAL",
                status=FILE_STATUS_AVAILABLE,
                storage_backend=str(settings.FILE_STORAGE_BACKEND or "local").lower(),
                storage_zone="ACTIVE",
                upload_source="SYSTEM",
                scan_required=False,
                scan_status=SCAN_NOT_REQUIRED,
                available_at=now,
            )
            db.add(row)
            db.flush()
            _register_binding(
                str(row.id),
                biz_type=biz_type,
                biz_id=biz_id,
                actor=actor,
                db=db,
            )
            db.commit()
            db.refresh(row)
            meta.update(_row_meta(row))
        finally:
            db.close()
    else:
        file_id = f"mem-{uuid.uuid4().hex[:12]}"
        meta["fileId"] = file_id
        _MEM_REGISTRY[file_id] = dict(meta)
        _MEM_TENANT[file_id] = tenant_id
        _MEM_OWNER[file_id] = owner_id or 0
        _MEM_META_EXTRA[file_id] = {
            "tenant_id": tenant_id,
            "owner_user_id": owner_id,
            "created_by": owner_id,
            "biz_type": biz_type,
            "biz_id": biz_id,
            "visibility": visibility,
            "security_level": security_level,
            "file_key": key,
            "file_name": filename,
            "status": FILE_STATUS_AVAILABLE,
            "scan_status": SCAN_NOT_REQUIRED,
            "scan_required": False,
            "is_deleted": False,
        }
    return meta


class _MemFile:
    def __init__(self, file_id: str):
        extra = _MEM_META_EXTRA.get(file_id) or {}
        reg = _MEM_REGISTRY.get(file_id) or {}
        self.id = file_id
        self.tenant_id = extra.get("tenant_id") or _MEM_TENANT.get(file_id) or 0
        self.owner_user_id = extra.get("owner_user_id") or _MEM_OWNER.get(file_id)
        self.created_by = extra.get("created_by")
        self.biz_type = extra.get("biz_type")
        self.biz_id = extra.get("biz_id")
        self.visibility = extra.get("visibility") or "PRIVATE"
        self.security_level = extra.get("security_level") or "NORMAL"
        self.is_deleted = bool(extra.get("is_deleted"))
        self.file_key = extra.get("file_key")
        self.file_name = extra.get("file_name")
        self.status = extra.get("status") or reg.get("status") or FILE_STATUS_AVAILABLE
        self.scan_status = extra.get("scan_status") or reg.get("scanStatus") or SCAN_NOT_REQUIRED
        self.scan_required = bool(extra.get("scan_required") or reg.get("scanRequired"))
        self.ext = reg.get("ext")
        self.size_bytes = reg.get("sizeBytes")
        self.sha256 = reg.get("sha256")
        self.created_at = None


def get_file_meta(
    file_id: str,
    user: dict | None = None,
    *,
    require_ready: bool = True,
) -> dict | None:
    actor = user or get_current_user_ctx() or {}
    if db_enabled() and str(file_id).isdigit():
        row = _load_file_row(file_id)
        if not row or not authorize_file_access(actor, row, "meta"):
            return None
        if require_ready:
            from app.services.file_scan_service import assert_file_ready_for_business

            assert_file_ready_for_business(file_id, user=actor)
        return _row_meta(row)
    if file_id in _MEM_REGISTRY:
        obj = _MemFile(file_id)
        if not authorize_file_access(actor, obj, "meta"):
            return None
        if require_ready and not _ready(obj):
            raise AppException(
                "FILE_NOT_READY",
                "文件尚未完成安全扫描，暂不可使用",
                http_status=409,
            )
        result = dict(_MEM_REGISTRY[file_id])
        result.update({
            "bizType": obj.biz_type,
            "bizId": obj.biz_id,
            "ownerUserId": obj.owner_user_id,
        })
        return result
    return None


def attachment_view(file_id: str | None) -> dict | None:
    if not file_id:
        return None
    meta = get_file_meta(file_id)
    if not meta:
        return None
    return {
        "fileId": meta["fileId"],
        "fileName": meta.get("fileName"),
        "ext": meta.get("ext"),
        "sizeBytes": meta.get("sizeBytes"),
    }


def resolve_download(
    file_id: str,
    *,
    allow_graduation_material: bool = False,
    user: dict | None = None,
):
    actor = user or get_current_user_ctx() or {}
    if db_enabled() and str(file_id).isdigit():
        row = _load_file_row(file_id)
        if not row or not authorize_file_access(actor, row, "download"):
            return None
        if (
            (row.biz_type or "").upper() == "GRADUATION_MATERIAL"
            and not allow_graduation_material
        ):
            return None
        path = get_backend().fetch_local(row.file_key)
        return (path, row.file_name or path.name) if path and path.exists() else None
    if file_id in _MEM_REGISTRY:
        obj = _MemFile(file_id)
        if not authorize_file_access(actor, obj, "download"):
            return None
        meta = _MEM_REGISTRY[file_id]
        path = get_backend().fetch_local(meta.get("fileKey"))
        return (path, meta.get("fileName") or path.name) if path and path.exists() else None
    return None


def bind_file_biz(
    file_id: str,
    biz_type: str,
    biz_id: str,
    user: dict | None = None,
    db=None,
) -> None:
    actor = user or get_current_user_ctx() or {}
    from app.services.file_scan_service import assert_file_ready_for_business

    assert_file_ready_for_business(file_id, user=actor)
    if db_enabled() and str(file_id).isdigit():
        from app.models.file import FileObject

        tenant_id = int(current_tenant_id() or 0)
        own_session = db is None
        session = db or get_sessionmaker()()
        try:
            row = session.scalars(select(FileObject).where(
                FileObject.id == int(file_id),
                FileObject.tenant_id == tenant_id,
                FileObject.is_deleted.is_(False),
            )).first()
            if not row:
                raise not_found("文件不存在")
            if not authorize_file_access(actor, row, "bind"):
                raise not_found("文件不存在")
            row.biz_type = (biz_type or row.biz_type or "").upper() or row.biz_type
            row.biz_id = str(biz_id)
            row.visibility = "BIZ_SCOPED"
            _register_binding(
                file_id,
                biz_type=row.biz_type or "ATTACHMENT",
                biz_id=str(biz_id),
                actor=actor,
                db=session,
            )
            session.commit() if own_session else session.flush()
        finally:
            if own_session:
                session.close()
        return
    if file_id in _MEM_META_EXTRA:
        _MEM_META_EXTRA[file_id].update({
            "biz_type": (biz_type or "").upper(),
            "biz_id": str(biz_id),
            "visibility": "BIZ_SCOPED",
        })


def _upload_max_size() -> int:
    try:
        from app.services.platform_service import safe_rule

        mb = safe_rule(int(current_tenant_id() or 0), "file", "uploadMaxSizeMb")
        return int(mb) * 1024 * 1024 if mb else MAX_SIZE
    except Exception:
        return MAX_SIZE


def _ensure_upload_allowed() -> None:
    try:
        from app.services.platform_service import feature_enabled

        allowed = feature_enabled(int(current_tenant_id() or 0), "fileUpload")
    except Exception:
        allowed = True
    if not allowed:
        raise AppException(
            "MODULE_NOT_AUTHORIZED",
            f"当前学校套餐未开通「文件上传」功能，请联系{settings.support_contact_display}",
        )
