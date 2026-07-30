"""扫描结果提交后的存储分区收口。

扫描数据库状态与对象复制分两次事务完成；复制失败时 CLEAN 文件重新关闭业务门，绝不出现
“数据库已可用、对象仍在隔离区”的假成功。
"""
from __future__ import annotations

from app.db.session import get_sessionmaker
from app.services.storage.keys import ZONE_PREFIX
from app.services.storage.production import promote_file_object


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
        if current_key.startswith(expected_prefix):
            row.storage_zone = target_zone
            db.commit()
            return {**result, "storageZone": target_zone, "objectKey": current_key}
        try:
            moved = promote_file_object(row, target_zone=target_zone)
            if target_zone == "CLEAN":
                row.storage_zone = "CLEAN"
                row.status = "AVAILABLE"
            else:
                row.storage_zone = "REJECTED"
                row.status = "REJECTED"
            db.commit()
            return {**result, **moved}
        except Exception as exc:  # noqa: BLE001 - fail closed and leave source bytes intact
            db.rollback()
            row = db.get(FileObject, int(file_id), with_for_update=True)
            if row and target_zone == "CLEAN":
                row.status = "QUARANTINED"
                row.storage_zone = "QUARANTINE"
                row.scan_status = "ERROR"
                row.scan_last_error = f"storage promotion failed: {exc}"[:2000]
                db.commit()
            return {**result, "storagePromotionError": str(exc), "readyForBusiness": False}
    finally:
        db.close()
