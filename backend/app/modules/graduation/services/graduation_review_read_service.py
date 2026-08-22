"""W7 formal review read projection with frozen FileVersion evidence.

This service is read-only. It mirrors the legacy /gd-reviews filters and pagination while
returning the W7 closure DTO (`version`, `materialId`, `fileVersionId`, `sourceSha256`).
Formal review writes remain owned by graduation_review_closure_service.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.tenant_scoped import tenant_get
from app.models import GraduationReview, GraduationStudent
from app.modules.graduation.services import graduation_review_closure_service as closure
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session


def list_reviews(page: int, page_size: int, gd_student_id=None, reviewer_name=None,
                 status=None, batch_id=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        q = select(GraduationReview).where(
            GraduationReview.tenant_id == _tid(),
            GraduationReview.is_deleted.is_(False),
            GraduationReview.gd_student_id.in_(scope_ids or [-1]),
        )
        if gd_student_id:
            q = q.where(GraduationReview.gd_student_id == int(gd_student_id))
        if batch_id:
            q = q.where(GraduationReview.gd_student_id.in_(select(GraduationStudent.id).where(
                GraduationStudent.tenant_id == _tid(),
                GraduationStudent.batch_id == int(batch_id),
                GraduationStudent.is_deleted.is_(False),
            )))
        if reviewer_name:
            q = q.where(GraduationReview.reviewer_name == reviewer_name)
        if status:
            q = q.where(GraduationReview.status == status)

        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(
            q.order_by(GraduationReview.id.desc())
            .offset((max(1, page) - 1) * page_size)
            .limit(page_size)
        ).all()
        return [
            closure._row(db, row, tenant_get(db, GraduationStudent, row.gd_student_id))
            for row in rows
        ], total
