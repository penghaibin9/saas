"""W7 formal review read/write overlay.

These routes deliberately keep the existing /graduation/gd-reviews paths and permission
identity. Reads expose the W7 frozen FileVersion/version DTO; writes keep the W7 evidence
locking authority in graduation_review_closure_service while W7.6 synchronizes derivative
UnifiedTodo lifecycle and reuses Review Center overdue/processing-time metrics.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.models import GraduationReview
from app.modules.graduation.routers.graduation_sensitive_router import _record_batch, _student_batch
from app.modules.graduation.schemas.graduation_review import ReviewAssignRequest, ReviewReturnRequest, ReviewSubmitRequest
from app.modules.graduation.services import graduation_review_w76_lifecycle_service as review
from app.modules.graduation.services import graduation_review_read_service as review_read

router = APIRouter(prefix="/graduation", tags=["毕业设计-W7评阅证据"])


def _sensitive_identity(fn):
    # Keep require_graduation_request_permission mapped to the already-frozen permission keys.
    fn.__module__ = "app.modules.graduation.routers.graduation_sensitive_router"
    return fn


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
    _record_batch(GraduationReview, rid, batchId)
    return success(review.submit_review(
        rid, body.score, body.opinion, expected_version=body.expectedVersion,
        file_version_id=body.fileVersionId, categories=body.categories, issues=body.issues,
        idempotency_key=body.idempotencyKey,
    ), message="已提交")


@router.post("/gd-reviews/{rid}/return")
@_sensitive_identity
def review_return(rid: str, body: ReviewReturnRequest, batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    _record_batch(GraduationReview, rid, batchId)
    return success(review.return_review(rid, body.reason), message="已退回")
