"""Shared, explicit export-size contract for internship ledgers."""
from app.core.exceptions import AppException

SAFE_EXPORT_MAX = 10000


def require_exportable(total: int) -> None:
    if total > SAFE_EXPORT_MAX:
        raise AppException("VALIDATION_ERROR",
                           f"导出结果共 {total} 行，超过单次安全上限 {SAFE_EXPORT_MAX} 行，请缩小筛选范围后重试")


def pack_export_meta(total: int, exported: int) -> dict:
    return {"totalRows": total, "exportedRows": exported, "truncated": exported < total,
            "safeExportMax": SAFE_EXPORT_MAX}
