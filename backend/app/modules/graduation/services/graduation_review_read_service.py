"""W7 formal review read projection with frozen FileVersion evidence.

This service is read-only. It mirrors the legacy /gd-reviews filters and pagination while
returning the W7 closure DTO (`version`, `materialId`, `fileVersionId`, `sourceSha256`).
Formal review writes remain owned by graduation_review_closure_service.

W7.4 hardens reviewer reads and statistics to stable reviewer_mentor_id ownership. A
reviewer relation to one student must never widen either endpoint to that student's other
formal review tasks or counts.
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

_REVIEW_STATUS_LABEL = {
    "ASSIGNED": "待评阅",
    "REVIEWING": "评阅中",
    "COMPLETED": "已完成",
    "RETURNED": "已退回",
}


def _role() -> str:
    user = get_current_user_ctx() or {}
    return str(user.get("currentRoleCode") or user.get("userType") or "").strip().upper()


def _base_review_query(db, *, batch_id=None):
    reviewer_role = _role() == "GD_REVIEWER"
    if reviewer_role:
        mentor = gid.current_user_mentor(db)
        if mentor is None:
            return None, True
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
        if batch_id:
            q = q.where(GraduationStudent.batch_id == int(batch_id))
        return q, True

    scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
    q = select(GraduationReview).where(
        GraduationReview.tenant_id == _tid(),
        GraduationReview.is_deleted.is_(False),
        GraduationReview.gd_student_id.in_(scope_ids or [-1]),
    )
    return q, False


def list_reviews(page: int, page_size: int, gd_student_id=None, reviewer_name=None,
                 status=None, batch_id=None) -> tuple[list[dict], int]:
    with session() as db:
        q, _ = _base_review_query(db, batch_id=batch_id)
        if q is None:
            return [], 0
        if gd_student_id:
            q = q.where(GraduationReview.gd_student_id == int(gd_student_id))
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


def review_stats(batch_id=None) -> dict:
    """Return legacy-shaped counts from the exact same actor/task scope as list_reviews."""
    with session() as db:
        q, _ = _base_review_query(db, batch_id=batch_id)
        if q is None:
            counts = {status: 0 for status in _REVIEW_STATUS_LABEL}
            total = 0
        else:
            total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
            counts = {
                status: int(db.scalar(
                    select(func.count()).select_from(
                        q.where(GraduationReview.status == status).subquery()
                    )
                ) or 0)
                for status in _REVIEW_STATUS_LABEL
            }
        return {
            "total": total,
            "byStatus": [
                {"status": status, "label": label, "count": counts[status]}
                for status, label in _REVIEW_STATUS_LABEL.items()
            ],
            "batchId": str(batch_id) if batch_id else None,
        }


__all__ = ["list_reviews", "review_stats"]
