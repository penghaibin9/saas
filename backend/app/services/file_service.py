"""
P4 · 真实文件上传：本地 UPLOAD_DIR 落盘 + sha256 + 白名单校验 + t_file_object 登记（DB 模式）。
接 MinIO/OSS 时仅替换 _store_to_disk 与 file_key 生成，契约字段不变。
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker

ALLOWED_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
               "png", "jpg", "jpeg", "gif", "zip", "txt", "csv"}
BLOCKED_EXT = {"exe", "js", "bat", "sh", "php", "jsp", "html", "svg"}
MAX_SIZE = 50 * 1024 * 1024

_MEM_REGISTRY: dict[str, dict] = {}  # DB_ENABLED=false 时的内存登记


def upload_dir() -> Path:
    d = Path(settings.UPLOAD_DIR or "./uploads")
    d.mkdir(parents=True, exist_ok=True)
    return d


def validate_ext(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in BLOCKED_EXT or ext not in ALLOWED_EXT:
        raise AppException("FILE_TYPE_NOT_ALLOWED", f"文件类型不允许：.{ext or '未知'}",
                           details={"allowed": sorted(ALLOWED_EXT)})
    return ext


async def store_upload(file, biz_type: str = "ATTACHMENT") -> dict:
    """校验 + 落盘 + 登记。返回契约字段（fileId/fileName/size/sha256/ext/bizType/storedAt）。"""
    filename = file.filename or "unnamed"
    ext = validate_ext(filename)
    sha = hashlib.sha256()
    size = 0
    key = f"{datetime.now():%Y%m%d}/{uuid.uuid4().hex}.{ext}"
    target = upload_dir() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_SIZE:
                out.close()
                target.unlink(missing_ok=True)
                raise AppException("FILE_TOO_LARGE", "文件超过 50MB 上限")
            sha.update(chunk)
            out.write(chunk)
    digest = sha.hexdigest()
    meta = {"fileName": filename, "ext": ext, "sizeBytes": size, "sha256": digest,
            "fileKey": key, "bizType": biz_type, "storedAt": datetime.now().isoformat(timespec="seconds")}
    if db_enabled():
        from app.models import FileObject
        db = get_sessionmaker()()
        try:
            row = FileObject(tenant_id=int(current_tenant_id() or 0) or 1000000000000000001,
                             file_key=key, file_name=filename, ext=ext,
                             mime_type=getattr(file, "content_type", None),
                             size_bytes=size, sha256=digest, biz_type=biz_type, status="STORED")
            db.add(row)
            db.commit()
            db.refresh(row)
            meta["fileId"] = str(row.id)
        finally:
            db.close()
    else:
        meta["fileId"] = f"mem-{uuid.uuid4().hex[:12]}"
        _MEM_REGISTRY[meta["fileId"]] = meta
    return meta


def get_file_meta(file_id: str) -> dict | None:
    if db_enabled() and file_id.isdigit():
        from app.models import FileObject
        db = get_sessionmaker()()
        try:
            row = db.get(FileObject, int(file_id))
            if not row or row.is_deleted:
                return None
            return {"fileId": str(row.id), "fileName": row.file_name, "ext": row.ext,
                    "sizeBytes": row.size_bytes, "sha256": row.sha256, "fileKey": row.file_key,
                    "bizType": row.biz_type, "storedAt": row.created_at.isoformat(timespec="seconds")}
        finally:
            db.close()
    return _MEM_REGISTRY.get(file_id)
