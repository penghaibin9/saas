"""W7 formal review read/write overlay.

These routes deliberately keep the existing /graduation/gd-reviews paths and permission
identity. Reads expose the W7 frozen FileVersion/version DTO; writes keep the W7 evidence
locking authority in graduation_review_closure_service while W7.6 synchronizes derivative
UnifiedTodo lifecycle and reuses Review Center overdue/processing-time metrics.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.exceptions import no_permission, not_found
from app.core.response import paginate, success
from app.core.security import get_current_user
from app.models import GraduationReview, GraduationStudent
from app.modules.graduation.routers.graduation_sensitive_router import _student_batch
from app.modules.graduation.schemas.graduation_review import ReviewAssignRequest, ReviewReturnRequest, ReviewSubmitRequest
from app.modules.graduation.services import graduation_identity as gid
from app.modules.graduation.services import graduation_review_w76_lifecycle_service as review
from app.modules.graduation.services import graduation_review_read_service as review_read
from app.modules.graduation.services.graduation_batch_context import assert_student_batch
from app.modules.graduation.services.graduation_scope_service import has_full_scope
from app.services.db_service import _tid, session

router = APIRouter(prefix="/graduation", tags=["毕业设计-W7评阅证据"])


def _sensitive_identity(fn):
    # Keep require_graduation_request_permission mapped to the already-frozen permission keys.
    fn.__module__ = "app.modules.graduation.routers.graduation_sensitive_router"
    return fn


def _review_batch(review_id, batch_id, *, require_assigned_reviewer: bool = False) -> int:
    """Fail closed on tenant/reviewer before exposing any student/batch metadata."""
    try:
        rid = int(review_id)
    except (TypeError, ValueError):
        raise not_found("评阅任务不存在") from None
    with session() as db:
        row = db.scalars(select(GraduationReview).where(
            GraduationReview.id == rid,
            GraduationReview.tenant_id == _tid(),
            GraduationReview.is_deleted.is_(False),
        )).first()
        if not row:
            raise not_found("评阅任务不存在")
        if require_assigned_reviewer and not has_full_scope():
            mentor = gid.current_user_mentor(db)
            assigned = getattr(row, "reviewer_mentor_id", None)
            if not mentor or not assigned or int(mentor.id) != int(assigned):
                raise no_permission("无权提交他人评阅任务")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(row.gd_student_id),
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.is_deleted.is_(False),
        )).first()
        assert_student_batch(student, batch_id)
        return int(student.id)


@router.get("/gd-reviews/stats")
@_sensitive_identity
def review_stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(review.review_stats(batch_id=batchId))


@router.get("/gd-reviews")
@_sensitive_identity
def review_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                gdStudentId: Optional[str] = None, reviewerName: Optional[str] = None,
                status: Optional[str] = None, batchId: int = Query(..., ge=1),
                user=Depends(get_current_user)):
    if gdStudentId:
        _student_batch(gdStudentId, batchId)
    items, total = review_read.list_reviews(page, pageSize, gd_student_id=gdStudentId,
                                            reviewer_name=reviewerName, status=status, batch_id=batchId)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-reviews/assign")
@_sensitive_identity
def review_assign(body: ReviewAssignRequest, batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    _student_batch(body.gdStudentId, batchId, for_update=True)
    return success(review.assign_review(body.gdStudentId, body.reviewerName, body.gdFinalId,
                                        reviewer_mentor_id=body.reviewerMentorId), message="已分配")


@router.post("/gd-reviews/{rid}/submit")
@_sensitive_identity
def review_submit(rid: str, body: ReviewSubmitRequest, batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    # Object authorization precedes SoD/business validation inside the closure service,
    # so an unrelated caller cannot probe advisor/reviewer conflict metadata.
    _review_batch(rid, batchId, require_assigned_reviewer=True)
    return success(review.submit_review(
        rid, body.score, body.opinion, expected_version=body.expectedVersion,
        file_version_id=body.fileVersionId, categories=body.categories, issues=body.issues,
        idempotency_key=body.idempotencyKey,
    ), message="已提交")


@router.post("/gd-reviews/{rid}/return")
@_sensitive_identity
def review_return(rid: str, body: ReviewReturnRequest, batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    _review_batch(rid, batchId)
    return success(review.return_review(rid, body.reason), message="已退回")
