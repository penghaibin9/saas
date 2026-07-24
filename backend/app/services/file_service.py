"""
真实文件上传：sha256 + 白名单 + t_file_object 登记 + 对象级授权。
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.permissions import has_permission, is_super_admin
from app.db.session import db_enabled, get_sessionmaker
from app.services.file_content_security import (
    FILE_STATUS_AVAILABLE,
    FILE_STATUS_QUARANTINED,
    is_downloadable_status,
    sanitize_filename,
    validate_content,
)
from app.services.storage import get_backend

ALLOWED_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
               "png", "jpg", "jpeg", "gif", "zip", "txt", "csv"}
BLOCKED_EXT = {"exe", "js", "bat", "sh", "php", "jsp", "html", "svg"}
MAX_SIZE = 50 * 1024 * 1024

_MEM_REGISTRY: dict[str, dict] = {}
_MEM_TENANT: dict[str, int] = {}
_MEM_OWNER: dict[str, int] = {}
_MEM_META_EXTRA: dict[str, dict] = {}

# biz_type → 查看该类附件所需 permissionCode（与学工附件等对齐；未登记则仅本人/管理员）
_BIZ_VIEW_PERM: dict[str, str] = {
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
    "ATTACHMENT": "studentAffairs.student.view",
}


def upload_dir() -> Path:
    d = Path(settings.UPLOAD_DIR or "./uploads")
    d.mkdir(parents=True, exist_ok=True)
    return d


def validate_ext(filename: str) -> str:
    safe = sanitize_filename(filename)
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    if ext in BLOCKED_EXT or ext not in ALLOWED_EXT:
        raise AppException("FILE_TYPE_NOT_ALLOWED", f"文件类型不允许：.{ext or '未知'}",
                           details={"allowed": sorted(ALLOWED_EXT)})
    return ext


def _require_tenant_id() -> int:
    try:
        tid = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tid = 0
    if db_enabled() and not tid:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝写入文件")
    if not tid:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝写入文件")
    return tid


def _actor_user_id(user: dict | None = None) -> int | None:
    from app.services.message_identity import resolve_message_user_id
    uid = resolve_message_user_id(user or get_current_user_ctx() or {})
    return uid or None


def _row_meta(row) -> dict:
    return {
        "fileId": str(row.id), "fileName": row.file_name, "ext": row.ext,
        "sizeBytes": row.size_bytes, "sha256": row.sha256, "fileKey": row.file_key,
        "bizType": row.biz_type, "bizId": row.biz_id,
        "ownerUserId": row.owner_user_id, "visibility": row.visibility,
        "securityLevel": row.security_level,
        "storedAt": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
        "createdBy": row.created_by,
    }


def authorize_file_access(user: dict, file_obj, action: str = "download") -> bool:
    """统一文件授权。不满足返回 False（调用方转统一 404，不泄露存在性）。"""
    if file_obj is None:
        return False
    try:
        tid = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tid = 0
    file_tid = int(getattr(file_obj, "tenant_id", 0) or 0)
    if not tid or not file_tid or tid != file_tid:
        return False
    if getattr(file_obj, "is_deleted", False):
        return False
    status = getattr(file_obj, "status", None)
    if action == "download" and not is_downloadable_status(status):
        return False
    if is_super_admin(user):
        return True

    uid = _actor_user_id(user)
    owner = getattr(file_obj, "owner_user_id", None) or getattr(file_obj, "created_by", None)
    if uid and owner and int(uid) == int(owner):
        return True

    # 历史无归属敏感/私有文件：不对普通用户开放（仅超管/全权管理员）
    visibility = (getattr(file_obj, "visibility", None) or "PRIVATE").upper()
    biz_type = (getattr(file_obj, "biz_type", None) or "").upper()
    biz_id = getattr(file_obj, "biz_id", None)
    if visibility == "PRIVATE" and not owner and not biz_id:
        return has_permission(user, "systemAdmin.file.manage") or has_permission(user, "*")

    # 学生本人：userType=STUDENT 且 biz 指向本人学号/学生 ID
    ut = (user.get("userType") or "").strip().upper()
    if ut == "STUDENT":
        return _student_owns_file(user, file_obj)

    # 业务对象权限
    if biz_type and biz_type in _BIZ_VIEW_PERM:
        if has_permission(user, _BIZ_VIEW_PERM[biz_type]):
            return True
    if has_permission(user, "systemAdmin.file.manage"):
        return True
    if has_permission(user, "*"):
        return True
    return False


def _student_owns_file(user: dict, file_obj) -> bool:
    """学生仅可访问明确归属本人的附件。"""
    student_no = str(user.get("studentNo") or "").strip()
    biz_id = str(getattr(file_obj, "biz_id", None) or "").strip()
    if student_no and biz_id and (biz_id == student_no or biz_id.endswith(f":{student_no}")):
        return True
    # biz_id 为学生主档数字 ID：对照令牌 studentId / 查库
    sid = str(user.get("studentId") or "").strip()
    if sid and biz_id and biz_id == sid:
        return True
    if biz_id.isdigit() and student_no and db_enabled():
        from sqlalchemy import select
        from app.models import StudentProfile
        db = get_sessionmaker()()
        try:
            row = db.scalars(select(StudentProfile).where(
                StudentProfile.id == int(biz_id),
                StudentProfile.tenant_id == int(current_tenant_id() or 0),
                StudentProfile.is_deleted.is_(False))).first()
            if row and row.student_no == student_no:
                return True
        finally:
            db.close()
    return False


def _load_file_row(file_id: str):
    """按当前租户加载；跨租户/不存在返回 None。"""
    tid = int(current_tenant_id() or 0)
    if not tid:
        return None
    if db_enabled() and str(file_id).isdigit():
        from sqlalchemy import select
        from app.models import FileObject
        db = get_sessionmaker()()
        try:
            return db.scalars(select(FileObject).where(
                FileObject.id == int(file_id),
                FileObject.tenant_id == tid,
                FileObject.is_deleted.is_(False))).first()
        finally:
            db.close()
    return None


async def store_upload(file, biz_type: str = "ATTACHMENT", *, biz_id: str | None = None,
                       user: dict | None = None, visibility: str = "BIZ_SCOPED",
                       security_level: str = "NORMAL") -> dict:
    """校验 + 落盘 + 登记。DB 模式强制租户上下文；服务端生成 fileKey。"""
    filename = sanitize_filename(file.filename or "unnamed")
    _ensure_upload_allowed()
    tid = _require_tenant_id()
    max_size = _upload_max_size()
    ext = validate_ext(filename)
    actor = user or get_current_user_ctx() or {}
    owner_id = _actor_user_id(actor)
    sha = hashlib.sha256()
    size = 0
    key = f"{datetime.now():%Y%m%d}/{uuid.uuid4().hex}.{ext}"
    backend = get_backend()
    target = backend.staging_path(key)
    chunks: list[bytes] = []
    try:
        with target.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_size:
                    raise AppException("FILE_TOO_LARGE",
                                       f"文件超过 {max_size // (1024 * 1024)}MB 上限（平台规则中心配置）")
                sha.update(chunk)
                out.write(chunk)
                if size <= 8 * 1024 * 1024:
                    chunks.append(chunk)
        data_for_scan = b"".join(chunks) if size <= 8 * 1024 * 1024 else target.read_bytes()
        declared = getattr(file, "content_type", None)
        mime, file_status = validate_content(
            filename=filename, declared_content_type=declared, data=data_for_scan, ext=ext, biz_type=biz_type)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    backend.persist(key, target)
    digest = sha.hexdigest()
    meta = {"fileName": filename, "ext": ext, "sizeBytes": size, "sha256": digest,
            "fileKey": key, "bizType": biz_type, "bizId": biz_id,
            "visibility": visibility, "securityLevel": security_level,
            "mimeType": mime, "status": file_status,
            "storedAt": datetime.now().isoformat(timespec="seconds")}
    if db_enabled():
        from app.models import FileObject
        db = get_sessionmaker()()
        try:
            row = FileObject(
                tenant_id=tid, file_key=key, file_name=filename, ext=ext,
                mime_type=mime, size_bytes=size, sha256=digest, biz_type=biz_type, biz_id=biz_id,
                owner_user_id=owner_id, created_by=owner_id,
                visibility=visibility or "BIZ_SCOPED",
                security_level=security_level or "NORMAL", status=file_status)
            db.add(row)
            db.commit()
            db.refresh(row)
            meta["fileId"] = str(row.id)
            meta["ownerUserId"] = owner_id
        finally:
            db.close()
    else:
        meta["fileId"] = f"mem-{uuid.uuid4().hex[:12]}"
        _MEM_REGISTRY[meta["fileId"]] = meta
        _MEM_TENANT[meta["fileId"]] = tid
        _MEM_OWNER[meta["fileId"]] = owner_id or 0
        _MEM_META_EXTRA[meta["fileId"]] = {
            "biz_type": biz_type, "biz_id": biz_id, "visibility": visibility,
            "security_level": security_level, "owner_user_id": owner_id,
            "created_by": owner_id, "tenant_id": tid, "is_deleted": False,
            "file_key": key, "file_name": filename, "status": file_status,
        }
    return meta


def store_bytes(data: bytes, filename: str, biz_type: str = "ATTACHMENT",
                mime_type: str | None = None, *, biz_id: str | None = None,
                user: dict | None = None, visibility: str = "PRIVATE",
                security_level: str = "NORMAL") -> dict:
    tid = _require_tenant_id()
    filename = sanitize_filename(filename)
    ext = validate_ext(filename)
    detected_mime, file_status = validate_content(
        filename=filename, declared_content_type=mime_type, data=data, ext=ext, biz_type=biz_type)
    key = f"{datetime.now():%Y%m%d}/{uuid.uuid4().hex}.{ext}"
    backend = get_backend()
    target = backend.staging_path(key)
    target.write_bytes(data)
    backend.persist(key, target)
    size = len(data)
    digest = hashlib.sha256(data).hexdigest()
    actor = user or get_current_user_ctx() or {}
    owner_id = _actor_user_id(actor)
    meta = {"fileName": filename, "ext": ext, "sizeBytes": size, "sha256": digest,
            "fileKey": key, "bizType": biz_type, "bizId": biz_id,
            "mimeType": detected_mime, "status": file_status,
            "storedAt": datetime.now().isoformat(timespec="seconds")}
    if db_enabled():
        from app.models import FileObject
        db = get_sessionmaker()()
        try:
            row = FileObject(
                tenant_id=tid, file_key=key, file_name=filename, ext=ext,
                mime_type=detected_mime, size_bytes=size, sha256=digest,
                biz_type=biz_type, biz_id=biz_id,
                owner_user_id=owner_id, created_by=owner_id,
                visibility=visibility or "PRIVATE",
                security_level=security_level or "NORMAL", status=file_status)
            db.add(row)
            db.commit()
            db.refresh(row)
            meta["fileId"] = str(row.id)
        finally:
            db.close()
    else:
        meta["fileId"] = f"mem-{uuid.uuid4().hex[:12]}"
        _MEM_REGISTRY[meta["fileId"]] = meta
        _MEM_TENANT[meta["fileId"]] = tid
        _MEM_OWNER[meta["fileId"]] = owner_id or 0
        _MEM_META_EXTRA[meta["fileId"]] = {
            "biz_type": biz_type, "biz_id": biz_id, "visibility": visibility,
            "security_level": security_level, "owner_user_id": owner_id,
            "created_by": owner_id, "tenant_id": tid, "is_deleted": False,
            "file_key": key, "file_name": filename, "status": file_status,
        }
    return meta


class _MemFile:
    """内存模式伪 FileObject，供 authorize_file_access 复用。"""
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
        self.ext = reg.get("ext")
        self.size_bytes = reg.get("sizeBytes")
        self.sha256 = reg.get("sha256")
        self.created_at = None


def get_file_meta(file_id: str, user: dict | None = None) -> dict | None:
    """元数据：对象级授权失败与不存在一律 None。"""
    user = user or get_current_user_ctx() or {}
    if db_enabled() and str(file_id).isdigit():
        row = _load_file_row(file_id)
        if not row or not authorize_file_access(user, row, "meta"):
            return None
        return _row_meta(row)
    if file_id in _MEM_REGISTRY:
        obj = _MemFile(file_id)
        if not authorize_file_access(user, obj, "meta"):
            return None
        m = dict(_MEM_REGISTRY[file_id])
        m.update({"bizType": obj.biz_type, "bizId": obj.biz_id, "ownerUserId": obj.owner_user_id})
        return m
    return None


def attachment_view(file_id: str | None) -> dict | None:
    if not file_id:
        return None
    m = get_file_meta(file_id)
    if not m:
        return None
    return {"fileId": m["fileId"], "fileName": m.get("fileName"),
            "ext": m.get("ext"), "sizeBytes": m.get("sizeBytes")}


def resolve_download(file_id: str, *, allow_graduation_material: bool = False, user: dict | None = None):
    """返回 (磁盘路径, 文件名)；无权限/不存在 → None（调用方 404）。"""
    user = user or get_current_user_ctx() or {}
    if db_enabled() and str(file_id).isdigit():
        row = _load_file_row(file_id)
        if not row or not authorize_file_access(user, row, "download"):
            return None
        if (row.biz_type or "").upper() == "GRADUATION_MATERIAL" and not allow_graduation_material:
            if not has_permission(user, "graduationDesign.view") and not has_permission(user, "*"):
                # 仍允许本人/已通过 authorize 的业务权限路径；此处仅额外拦截裸下载旁路
                if not (row.owner_user_id and _actor_user_id(user) == row.owner_user_id):
                    return None
        path = get_backend().fetch_local(row.file_key)
        if not path or not path.exists():
            return None
        return path, row.file_name or path.name
    if file_id in _MEM_REGISTRY:
        obj = _MemFile(file_id)
        if not authorize_file_access(user, obj, "download"):
            return None
        m = _MEM_REGISTRY[file_id]
        path = get_backend().fetch_local(m.get("fileKey"))
        if not path or not path.exists():
            return None
        return path, m.get("fileName") or path.name
    return None


def bind_file_biz(file_id: str, biz_type: str, biz_id: str, user: dict | None = None) -> None:
    """业务服务在关联附件时回写 biz 绑定，便于后续对象级授权。"""
    user = user or get_current_user_ctx() or {}
    if db_enabled() and str(file_id).isdigit():
        from sqlalchemy import select
        from app.models import FileObject
        tid = int(current_tenant_id() or 0)
        db = get_sessionmaker()()
        try:
            row = db.scalars(select(FileObject).where(
                FileObject.id == int(file_id), FileObject.tenant_id == tid)).first()
            if not row:
                return
            if not authorize_file_access(user, row, "bind"):
                return
            row.biz_type = (biz_type or row.biz_type or "").upper() or row.biz_type
            row.biz_id = str(biz_id)
            row.visibility = "BIZ_SCOPED"
            db.commit()
        finally:
            db.close()
        return
    if file_id in _MEM_META_EXTRA:
        _MEM_META_EXTRA[file_id]["biz_type"] = (biz_type or "").upper()
        _MEM_META_EXTRA[file_id]["biz_id"] = str(biz_id)
        _MEM_META_EXTRA[file_id]["visibility"] = "BIZ_SCOPED"


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
        from app.core.config import settings
        raise AppException(
            "MODULE_NOT_AUTHORIZED",
            f"当前学校套餐未开通「文件上传」功能，请联系{settings.support_contact_display}")
