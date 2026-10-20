"""系统生成的大文件路径型写入：分块哈希，不整文件载入内存。"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.models.file import FileObject
from app.services import file_service
from app.services.db_service import _tid, session
from app.services.file_content_security import FILE_STATUS_AVAILABLE, sanitize_filename, validate_content_path
from app.services.file_scan_constants import SCAN_NOT_REQUIRED
from app.services.message_identity import resolve_message_user_id
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
    source_path,
    filename,
    biz_type="ATTACHMENT",
    mime_type=None,
    *,
    biz_id=None,
    user=None,
    visibility="PRIVATE",
    security_level="NORMAL",
    db=None,
):
    source = Path(source_path)
    if not source.is_file():
        raise AppException("FILE_NOT_FOUND", "系统生成文件不存在")
    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower().lstrip(".")
    if not ext:
        raise AppException("FILE_TYPE_NOT_ALLOWED", "系统生成文件缺少扩展名")
    detected_mime, _ = validate_content_path(
        filename=safe_name,
        declared_content_type=mime_type,
        path=source,
        ext=ext,
        biz_type=biz_type,
        source="SYSTEM",
    )
    key = f"{_tid()}/{datetime.utcnow():%Y%m%d}/{uuid.uuid4().hex}.{ext}"
    backend = get_backend()
    staged = backend.staging_path(key)
    size, digest = _copy_and_hash(source, staged)
    final_path = backend.persist(key, staged)
    actor = user or get_current_user_ctx() or {}
    uid = resolve_message_user_id(actor) or None
    owns = db is None
    working = db or session()
    try:
        row = FileObject(
            tenant_id=_tid(),
            file_key=key,
            file_name=safe_name,
            ext=ext,
            mime_type=detected_mime,
            size_bytes=size,
            sha256=digest,
            biz_type=biz_type,
            biz_id=str(biz_id) if biz_id is not None else None,
            owner_user_id=uid,
            created_by=uid,
            visibility=visibility or "PRIVATE",
            security_level=security_level or "NORMAL",
            status=FILE_STATUS_AVAILABLE,
            storage_backend="local",
            storage_zone="ACTIVE",
            upload_source="SYSTEM",
            scan_required=False,
            scan_status=SCAN_NOT_REQUIRED,
            available_at=datetime.utcnow(),
        )
        working.add(row)
        working.flush()
        if biz_id is not None:
            file_service._bind_in_session(working, row, biz_type, str(biz_id), actor)
        if owns:
            working.commit()
            working.refresh(row)
        return {
            "fileId": str(row.id),
            "fileName": row.file_name,
            "ext": row.ext,
            "mimeType": row.mime_type,
            "sizeBytes": int(row.size_bytes or 0),
            "sha256": row.sha256,
            "fileKey": row.file_key,
            "bizType": row.biz_type,
            "bizId": row.biz_id,
            "status": row.status,
            "scanStatus": row.scan_status,
            "readyForBusiness": True,
        }
    except Exception:
        if owns:
            working.rollback()
        try:
            Path(final_path).unlink(missing_ok=True)
        except Exception:
            pass
        raise
    finally:
        if owns:
            working.close()
