"""Task-scoped Review Center student sets.

A formal reviewer is authorized by stable ``reviewer_mentor_id``. Review Center must not
materialize an entire batch and run one relation query per student just to discover that
set; resolve it in one tenant/batch-scoped join instead. No real-name fallback is allowed
on this production path.
"""
from __future__ import annotations

from sqlalchemy import and_, select

from app.models import GraduationReview, GraduationStudent
from app.services.db_service import _tid


def reviewer_student_ids(db, *, batch_id: int, reviewer_mentor_id: int) -> list[int]:
    reviewer_id = int(reviewer_mentor_id)
    rows = db.scalars(
        select(GraduationStudent.id)
        .join(
            GraduationReview,
            and_(
                GraduationReview.gd_student_id == GraduationStudent.id,
                GraduationReview.tenant_id == GraduationStudent.tenant_id,
            ),
        )
        .where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.batch_id == int(batch_id),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.is_deleted.is_(False),
            GraduationReview.tenant_id == _tid(),
            GraduationReview.reviewer_mentor_id == reviewer_id,
            GraduationReview.is_deleted.is_(False),
        )
        .distinct()
    ).all()
    return [int(student_id) for student_id in rows]


__all__ = ["reviewer_student_ids"]
