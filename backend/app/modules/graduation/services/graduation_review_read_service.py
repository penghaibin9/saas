"""W7 formal review read projection with frozen FileVersion evidence.

This service is read-only. It mirrors the legacy /gd-reviews filters and pagination while
returning the W7 closure DTO (`version`, `materialId`, `fileVersionId`, `sourceSha256`).
Formal review writes remain owned by graduation_review_closure_service.

W7.4 hardens reviewer reads to stable reviewer_mentor_id ownership. A reviewer relation to
one student must never widen this endpoint to that student's other formal review tasks.
"""
from __future__ import annotations

from sqlalchemy import and_, func, select

from app.core.context import get_current_user_ctx
from app.core.tenant_scoped import tenant_get
from app.models import GraduationReview, GraduationStudent
from app.modules.graduation.services import graduation_identity as gid
from app.modules.graduation.services import graduation_review_closure_service as closure
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session


def _role() -> str:
    user = get_current_user_ctx() or {}
    return str(user.get("currentRoleCode") or user.get("userType") or "").strip().upper()


def list_reviews(page: int, page_size: int, gd_student_id=None, reviewer_name=None,
                 status=None, batch_id=None) -> tuple[list[dict], int]:
    with session() as db:
        reviewer_role = _role() == "GD_REVIEWER"
        if reviewer_role:
            mentor = gid.current_user_mentor(db)
            if mentor is None:
                return [], 0
            # Task authority is reviewer_mentor_id. Join the active tenant student row so
            # a stale/cross-tenant FK cannot become a readable task. No name fallback.
            q = select(GraduationReview).join(
                GraduationStudent,
                and_(
                    GraduationStudent.id == GraduationReview.gd_student_id,
                    GraduationStudent.tenant_id == GraduationReview.tenant_id,
                ),
            ).where(
                GraduationReview.tenant_id == _tid(),
                GraduationReview.is_deleted.is_(False),
                GraduationReview.reviewer_mentor_id == int(mentor.id),
                GraduationStudent.tenant_id == _tid(),
                GraduationStudent.record_status == "ACTIVE",
                GraduationStudent.is_deleted.is_(False),
            )
        else:
            scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
            q = select(GraduationReview).where(
                GraduationReview.tenant_id == _tid(),
                GraduationReview.is_deleted.is_(False),
                GraduationReview.gd_student_id.in_(scope_ids or [-1]),
            )

        if gd_student_id:
            q = q.where(GraduationReview.gd_student_id == int(gd_student_id))
        if batch_id:
            if reviewer_role:
                q = q.where(GraduationStudent.batch_id == int(batch_id))
            else:
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
