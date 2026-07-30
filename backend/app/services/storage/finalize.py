"""扫描结果提交后的存储分区收口。

ClamAV CLEAN 只是恶意样本结论；直传文件还必须在隔离区完成扩展名/MIME/magic/OOXML/ZIP
结构校验和 SHA-256 核验，之后才允许复制到 clean。任何一步失败都重新关闭业务门。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.services.file_content_security import validate_content_path
from app.services.storage import get_backend
from app.services.storage.keys import ZONE_PREFIX
from app.services.storage.production import hash_local_path, promote_file_object


def _validate_clean_candidate(row) -> None:
    key = str(row.object_key or row.file_key or "")
    path = get_backend().fetch_local(key)
    if not path or not path.exists():
        raise AppException("FILE_STORAGE_OBJECT_MISSING", "隔离区对象不存在")
    actual_sha = hash_local_path(path)
    expected_sha = str(row.sha256 or "").lower().strip()
    if expected_sha and actual_sha != expected_sha:
        raise AppException(
            "FILE_UPLOAD_HASH_MISMATCH",
            "文件 SHA-256 与上传会话声明不一致",
            details={"expected": expected_sha, "actual": actual_sha},
        )
    mime, _status = validate_content_path(
        filename=row.file_name or f"file.{row.ext or 'bin'}",
        declared_content_type=row.mime_type,
        path=path,
        ext=row.ext or "",
        biz_type=row.biz_type or "ATTACHMENT",
        source="USER",
    )
    row.sha256 = actual_sha
    row.mime_type = mime


def finalize_scan_storage(result: dict) -> dict:
    file_id = str(result.get("fileId") or "")
    scan_status = str(result.get("scanStatus") or "").upper()
    if not result.get("processed") or not file_id.isdigit() or scan_status not in {"CLEAN", "INFECTED"}:
        return result

    from app.models.file import FileObject

    target_zone = "CLEAN" if scan_status == "CLEAN" else "REJECTED"
    db = get_sessionmaker()()
    try:
        row = db.get(FileObject, int(file_id), with_for_update=True)
        if not row or row.is_deleted:
            return result
        current_key = str(row.object_key or row.file_key or "").lstrip("/")
        expected_prefix = f"{ZONE_PREFIX[target_zone]}/{int(row.tenant_id)}/"
        try:
            if target_zone == "CLEAN":
                _validate_clean_candidate(row)
            if current_key.startswith(expected_prefix):
                row.storage_zone = target_zone
                row.status = "AVAILABLE" if target_zone == "CLEAN" else "REJECTED"
                db.commit()
                return {
                    **result,
                    "storageZone": target_zone,
                    "objectKey": current_key,
                    "sha256": row.sha256,
                    "mimeType": row.mime_type,
                }
            moved = promote_file_object(row, target_zone=target_zone)
            if target_zone == "CLEAN":
                row.storage_zone = "CLEAN"
                row.status = "AVAILABLE"
            else:
                row.storage_zone = "REJECTED"
                row.status = "REJECTED"
            db.commit()
            return {**result, **moved, "sha256": row.sha256, "mimeType": row.mime_type}
        except Exception as exc:  # noqa: BLE001 - fail closed and leave source bytes intact
            db.rollback()
            row = db.get(FileObject, int(file_id), with_for_update=True)
            if row and target_zone == "CLEAN":
                row.status = "QUARANTINED"
                row.storage_zone = "QUARANTINE"
                row.scan_status = "ERROR"
                row.scan_last_error = f"storage/content promotion failed: {exc}"[:2000]
                db.commit()
            return {
                **result,
                "storagePromotionError": str(exc),
                "readyForBusiness": False,
            }
    finally:
        db.close()
