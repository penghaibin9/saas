"""SQL-paged read path for internship intentions.

This module intentionally reuses the canonical InternshipRecord SQL scope adapter and the existing
row projection. It changes only query shape: scope/keyword/count/pagination are evaluated by MySQL,
so a 20-row page no longer materializes and hydrates the whole internship batch.
"""
from __future__ import annotations

from sqlalchemy import func, or_, select

from app.models import InternshipIntention, InternshipRecord, StudentProfile
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.services.db_service import _tid, session


def list_intentions(user, *, page: int, page_size: int, keyword=None, status=None, batch_id=None):
    from app.modules.internship.services import internship_match_service as legacy
    from app.modules.internship.services.internship_batch_context import resolve_batch

    page_no = max(1, int(page))
    size = max(1, int(page_size))
    with session() as db:
        batch = resolve_batch(db, batch_id)
        base = (
            select(InternshipIntention)
            .join(
                InternshipRecord,
                (InternshipRecord.id == InternshipIntention.record_id)
                & (InternshipRecord.tenant_id == InternshipIntention.tenant_id)
                & InternshipRecord.is_deleted.is_(False),
            )
            .join(
                StudentProfile,
                (StudentProfile.id == InternshipIntention.student_id)
                & (StudentProfile.tenant_id == InternshipIntention.tenant_id)
                & StudentProfile.is_deleted.is_(False),
            )
            .where(
                InternshipIntention.tenant_id == _tid(),
                InternshipIntention.is_deleted.is_(False),
                InternshipIntention.batch_id == batch.id,
            )
        )
        if status:
            base = base.where(InternshipIntention.status == status)
        kw = str(keyword or "").strip()
        if kw:
            base = base.where(or_(
                StudentProfile.real_name.contains(kw, autoescape=True),
                StudentProfile.student_no.contains(kw, autoescape=True),
                InternshipIntention.preferred_city.contains(kw, autoescape=True),
                InternshipIntention.preferred_industry.contains(kw, autoescape=True),
            ))
        base = apply_internship_record_scope(base, user)

        count_query = select(func.count()).select_from(base.order_by(None).subquery())
        total = int(db.scalar(count_query) or 0)
        rows = db.scalars(
            base.order_by(InternshipIntention.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [legacy._intention_row(db, row) for row in rows], total
