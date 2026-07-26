"""Reconciliation export for unified student-affairs history imports."""

from sqlalchemy import func, select

from app.services.db_service import _iso, _tid, session


def list_history(page=1, page_size=5000):
    from app.models import AffairsAuditTrail

    with session() as db:
        conds = (
            AffairsAuditTrail.tenant_id == _tid(),
            AffairsAuditTrail.biz_type.like("HISTORY_IMPORT_%"),
            AffairsAuditTrail.is_deleted.is_(False),
        )
        total = int(db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(*conds)) or 0)
        rows = db.scalars(
            select(AffairsAuditTrail).where(*conds)
            .order_by(AffairsAuditTrail.id)
            .offset((max(1, int(page)) - 1) * int(page_size))
            .limit(int(page_size))
        ).all()
        return [{
            "bizType": row.biz_type.removeprefix("HISTORY_IMPORT_"),
            "recordId": str(row.biz_id or ""),
            "historyNo": (row.detail or "").removeprefix("historyNo="),
            "operator": row.operator or "未记录",
            "importedAt": _iso(row.occurred_at),
        } for row in rows], total
