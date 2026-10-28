"""Shared COUNT-before-projection export contract for internship ledgers."""
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.models import InternshipAuditTrail
from app.services.db_service import _tid

SAFE_EXPORT_MAX = 10000


def require_exportable(total: int) -> None:
    if total > SAFE_EXPORT_MAX:
        raise AppException("VALIDATION_ERROR",
                           f"导出结果共 {total} 行，超过单次安全上限 {SAFE_EXPORT_MAX} 行，请缩小筛选范围后重试")


def pack_export_meta(total: int, exported: int) -> dict:
    return {"totalRows": total, "exportedRows": exported, "truncated": exported < total,
            "safeExportMax": SAFE_EXPORT_MAX}


def count_before_projection(db, filtered_query) -> int:
    total = int(db.scalar(select(func.count()).select_from(filtered_query.subquery())) or 0)
    require_exportable(total)
    return total


def write_export_audit(db, ledger: str, total: int, user=None, filters=None,
                       sensitive_fields=None) -> None:
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=0, target_type="EXPORT",
        action="SENSITIVE_EXPORT" if sensitive_fields else "EXPORT",
        operator_name=(user or {}).get("realName") or "系统",
        detail_json={
            "ledger": ledger, "totalRows": total, "filters": filters or {},
            "sensitiveFields": sensitive_fields or [],
            "actorUserId": str((user or {}).get("userId") or ""),
            "actorRole": (user or {}).get("currentRoleCode") or "",
        }, occurred_at=datetime.utcnow()))


def load_export_rows(list_func, /, **filters):
    """Use the list query's identical filter contract, but reject before row projection."""
    _empty, total = list_func(1, 0, **filters)
    require_exportable(total)
    if total == 0:
        return [], 0
    rows, checked_total = list_func(1, total, **filters)
    if checked_total != total:
        raise AppException("DATA_CONFLICT", "导出预检后数据已变化，请重试")
    return rows, total
