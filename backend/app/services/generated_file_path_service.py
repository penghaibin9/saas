"""系统生成文件的路径型可信写入。

用于大型 ZIP/XLSX/PDF：生成过程写临时文件，随后按块计算 SHA-256、执行路径级
内容校验并持久化，不把整个文件读入进程内存。最终仍登记同一个 FileObject 和业务绑定。
"""
from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.context import get_current_user_ctx
from app.db.session import db_enabled, get_sessionmaker
from app.services import file_service
from app.services.file_content_security import FILE_STATUS_AVAILABLE, sanitize_filename, validate_content_path
from app.services.file_scan_constants import SCAN_NOT_REQUIRED
from app.services.storage import get_backend

CHUNK_SIZE = 1024 * 1024


def _copy_and_hash(source: Path, target: Path) -> tuple[int, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as reader, target.open("wb") as writer:
        while True:
            chunk = reader.read(CHUNK_SIZE)
            if not chunk:
                break
            writer.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def store_generated_path(
    source_path: str | Path,
    filename: str,
    biz_type: str = "ATTACHMENT",
    mime_type: str | None = None,
    *,
    biz_id: str | None = None,
    user: dict | None = None,
    visibility: str = "PRIVATE",
    security_level: str = "NORMAL",
    db=None,
) -> dict:
    """把系统生成的本地临时文件安全登记为 FileObject，不整文件读内存。"""
    source = Path(source_path)
    if not source.is_file():
        from app.core.exceptions import AppException

        raise AppException("FILE_NOT_FOUND", "系统生成文件不存在")
    tenant_id = file_service._require_tenant_id()  # noqa: SLF001
    safe_name = sanitize_filename(filename)
    ext = file_service.validate_ext(safe_name)
    detected_mime, _status = validate_content_path(
        filename=safe_name,
        declared_content_type=mime_type,
        path=source,
        ext=ext,
        biz_type=biz_type,
        source="SYSTEM",
    )
    key = f"{datetime.now():%Y%m%d}/{uuid.uuid4().hex}.{ext}"
    backend = get_backend()
    staged = backend.staging_path(key)
    try:
        size, sha256 = _copy_and_hash(source, staged)
        backend.persist(key, staged)
    except Exception:
        staged.unlink(missing_ok=True)
        raise

    now = datetime.utcnow()
    actor = user or get_current_user_ctx() or {}
    owner_id = file_service._actor_user_id(actor)  # noqa: SLF001
    meta = {
        "fileName": safe_name,
        "ext": ext,
        "sizeBytes": size,
        "sha256": sha256,
        "fileKey": key,
        "bizType": biz_type,
        "bizId": biz_id,
        "mimeType": detected_mime,
        "status": FILE_STATUS_AVAILABLE,
        "scanRequired": False,
        "scanStatus": SCAN_NOT_REQUIRED,
        "readyForBusiness": True,
        "storedAt": now.isoformat(timespec="seconds"),
    }
    if db_enabled():
        from app.models.file import FileObject

        owns_db = db is None
        working_db = db or get_sessionmaker()()
        try:
            row = FileObject(
                tenant_id=tenant_id,
                file_key=key,
                file_name=safe_name,
                ext=ext,
                mime_type=detected_mime,
                size_bytes=size,
                sha256=sha256,
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
            working_db.add(row)
            working_db.flush()
            file_service._register_binding(  # noqa: SLF001
                str(row.id), biz_type=biz_type, biz_id=biz_id, actor=actor, db=working_db
            )
            if owns_db:
                working_db.commit()
                working_db.refresh(row)
            meta.update(file_service._row_meta(row))  # noqa: SLF001
        except Exception:
            if owns_db:
                working_db.rollback()
            try:
                backend.delete(key)
            except Exception:
                pass
            raise
        finally:
            if owns_db:
                working_db.close()
    else:
        file_id = f"mem-{uuid.uuid4().hex[:12]}"
        meta["fileId"] = file_id
        file_service._MEM_REGISTRY[file_id] = dict(meta)  # noqa: SLF001
        file_service._MEM_TENANT[file_id] = tenant_id  # noqa: SLF001
        file_service._MEM_OWNER[file_id] = owner_id or 0  # noqa: SLF001
        file_service._MEM_META_EXTRA[file_id] = {  # noqa: SLF001
            "tenant_id": tenant_id,
            "owner_user_id": owner_id,
            "created_by": owner_id,
            "biz_type": biz_type,
            "biz_id": biz_id,
            "visibility": visibility,
            "security_level": security_level,
            "file_key": key,
            "file_name": safe_name,
            "status": FILE_STATUS_AVAILABLE,
            "scan_status": SCAN_NOT_REQUIRED,
            "scan_required": False,
            "is_deleted": False,
        }
    return meta
