"""事务安全的存储分区提升。

准备阶段只复制并核验目标对象、更新 ORM 内存元数据，不删除源对象。调用者必须先提交数据库元数据，
随后再调用 ``cleanup_promoted_source``。这样数据库提交失败时仍保留原隔离对象；提交后删源失败只会
留下可由孤儿巡检清理的重复对象，不会让 FileObject 指向不存在的字节。
"""
from __future__ import annotations

import os
from datetime import datetime

from app.core.exceptions import AppException
from app.services.storage import get_backend
from app.services.storage.keys import build_object_key, normalize_zone


def prepare_file_object_promotion(file_obj, *, target_zone: str) -> dict:
    zone = normalize_zone(target_zone)
    backend = get_backend()
    source_key = str(getattr(file_obj, "object_key", None) or file_obj.file_key)
    target_key = build_object_key(
        zone=zone,
        tenant_id=int(file_obj.tenant_id),
        ext=file_obj.ext or "bin",
    )
    expected_size = int(file_obj.size_bytes or 0)

    if getattr(backend, "kind", "") == "cos":
        copied = backend.copy_object(source_key, target_key)
        actual_size = int(copied.get("sizeBytes") or 0)
        if actual_size != expected_size:
            backend.delete(target_key)
            raise AppException(
                "FILE_STORAGE_VERIFY_FAILED",
                "COS 分区复制后大小核验失败",
                details={"expected": expected_size, "actual": actual_size},
            )
        file_obj.bucket_name = backend.bucket_name
        file_obj.etag = copied.get("etag") or file_obj.etag
    else:
        source = backend.fetch_local(source_key)
        if not source or not source.exists():
            raise AppException("FILE_STORAGE_OBJECT_MISSING", "源文件不存在")
        target = backend.staging_path(target_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".part")
        partial.unlink(missing_ok=True)
        try:
            with source.open("rb") as reader, partial.open("wb") as writer:
                while chunk := reader.read(1024 * 1024):
                    writer.write(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            if partial.stat().st_size != expected_size:
                raise AppException("FILE_STORAGE_VERIFY_FAILED", "本地分区复制后大小核验失败")
            partial.replace(target)
        except Exception:
            partial.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            raise
        file_obj.bucket_name = None
        file_obj.etag = None

    file_obj.file_key = target_key
    file_obj.object_key = target_key
    file_obj.storage_zone = zone
    file_obj.storage_verified_at = datetime.utcnow()
    return {
        "sourceObjectKey": source_key,
        "objectKey": target_key,
        "storageZone": zone,
        "etag": file_obj.etag,
        "cleanupSourceAfterCommit": source_key != target_key,
    }


def cleanup_promoted_source(source_key: str, target_key: str) -> dict:
    source = str(source_key or "")
    target = str(target_key or "")
    if not source or source == target:
        return {"sourceCleanupPending": False}
    try:
        get_backend().delete(source)
        return {"sourceCleanupPending": False, "sourceObjectKey": source}
    except Exception as exc:  # noqa: BLE001 - target is already committed and authoritative
        return {
            "sourceCleanupPending": True,
            "sourceObjectKey": source,
            "sourceCleanupError": str(exc)[:1000],
        }
