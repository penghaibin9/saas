"""Read-only enterprise position search adapter over canonical InternshipPosition Authority."""
from __future__ import annotations

from sqlalchemy import func, or_, select

from app.models import InternshipPosition
from app.modules.internship.services import internship_enterprise_position_service as position_svc


def _escape_like(value: str) -> str:
    """Treat %, _ and backslash as literal keyword characters."""
    return str(value or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_positions_in_tx(
    db,
    *,
    context,
    page: int,
    page_size: int,
    status: str | None = None,
    keyword: str | None = None,
) -> dict:
    q = position_svc._position_query(context)
    if status:
        q = q.where(InternshipPosition.status == str(status).upper())
    text = str(keyword or "").strip()
    if text:
        for token in [part for part in text.split() if part]:
            pattern = f"%{_escape_like(token)}%"
            q = q.where(or_(
                InternshipPosition.title.like(pattern, escape="\\"),
                InternshipPosition.company_name.like(pattern, escape="\\"),
                InternshipPosition.category.like(pattern, escape="\\"),
                InternshipPosition.work_location.like(pattern, escape="\\"),
                InternshipPosition.major_requirement.like(pattern, escape="\\"),
            ))
    total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = db.scalars(
        q.order_by(InternshipPosition.id.desc())
        .offset((max(1, page) - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [position_svc._position_row(row) for row in rows],
        "total": total,
        "page": max(1, page),
        "pageSize": page_size,
    }
