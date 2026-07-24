"""毕业设计中心 · 查重记录 + 教师评阅 API
（/api/v1/graduation/gd-plagiarism/*，/api/v1/graduation/gd-reviews/*）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation_review import (PlagiarismDisputeRequest, PlagiarismDisputeReview,
                                           PlagiarismResultRequest, PlagiarismSubmitRequest,
                                           ReviewAssignRequest, ReviewReturnRequest, ReviewSubmitRequest)
from app.services import audit_log
from app.modules.graduation.services import graduation_review_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-查重与评阅"])


# ═══ 查重 ═══

@router.get("/gd-plagiarism/stats", summary="查重统计")
def gd_plagiarism_stats(user=Depends(get_current_user)):
    return success(svc.plagiarism_stats())


@router.get("/gd-plagiarism", summary="查重记录列表")
def gd_plagiarism_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                       gdStudentId: Optional[str] = None, status: Optional[str] = None,
                       user=Depends(get_current_user)):
    items, total = svc.list_plagiarism(page, pageSize, gd_student_id=gdStudentId, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-plagiarism/{gd_student_id}/submit", summary="发起查重")
def gd_plagiarism_submit(gd_student_id: str, body: PlagiarismSubmitRequest, user=Depends(get_current_user)):
    result = svc.submit_plagiarism(gd_student_id, body.gdFinalId)
    audit_log.record("发起查重", f"graduation-plagiarism:{result['id']}")
    return success(result, message="已提交检测")


@router.post("/gd-plagiarism/{pid}/result", summary="回填查重结果（检测中→完成）")
def gd_plagiarism_result(pid: str, body: PlagiarismResultRequest, user=Depends(get_current_user)):
    result = svc.set_plagiarism_result(pid, body.rate, body.reportUrl)
    audit_log.record("回填查重结果", f"graduation-plagiarism:{pid}", detail={"rate": body.rate})
    return success(result, message="已回填")


@router.post("/gd-plagiarism/{pid}/dispute", summary="申请复查（原因≥5字，仅超标可申请）")
def gd_plagiarism_dispute(pid: str, body: PlagiarismDisputeRequest, user=Depends(get_current_user)):
    result = svc.dispute_plagiarism(pid, body.reason)
    audit_log.record("申请查重复查", f"graduation-plagiarism:{pid}")
    return success(result, message="已提交复查申请")


@router.post("/gd-plagiarism/{pid}/dispute/review", summary="审核复查申请")
def gd_plagiarism_dispute_review(pid: str, body: PlagiarismDisputeReview, user=Depends(get_current_user)):
    result = svc.review_dispute(pid, body.action, body.comment)
    audit_log.record("审核查重复查", f"graduation-plagiarism:{pid}", detail={"action": body.action})
    return success(result, message="已审核")


# ═══ 教师评阅 ═══

@router.get("/gd-reviews/stats", summary="评阅统计")
def gd_review_stats(user=Depends(get_current_user)):
    return success(svc.review_stats())


@router.get("/gd-reviews", summary="评阅任务列表")
def gd_review_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   gdStudentId: Optional[str] = None, reviewerName: Optional[str] = None,
                   status: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_reviews(page, pageSize, gd_student_id=gdStudentId,
                                    reviewer_name=reviewerName, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-reviews/assign", summary="分配评阅任务（SoD：评阅人不得是指导教师）")
def gd_review_assign(body: ReviewAssignRequest, user=Depends(get_current_user)):
    result = svc.assign_review(
        body.gdStudentId, body.reviewerName, body.gdFinalId,
        reviewer_mentor_id=body.reviewerMentorId)
    audit_log.record("分配评阅任务", f"graduation-review:{result['id']}")
    return success(result, message="已分配")


@router.post("/gd-reviews/{rid}/submit", summary="提交评阅（评分+意见）")
def gd_review_submit(rid: str, body: ReviewSubmitRequest, user=Depends(get_current_user)):
    result = svc.submit_review(rid, body.score, body.opinion)
    audit_log.record("提交评阅", f"graduation-review:{rid}", detail={"score": body.score})
    return success(result, message="已提交")


@router.post("/gd-reviews/{rid}/return", summary="退回重评（原因≥5字）")
def gd_review_return(rid: str, body: ReviewReturnRequest, user=Depends(get_current_user)):
    result = svc.return_review(rid, body.reason)
    audit_log.record("退回重评", f"graduation-review:{rid}")
    return success(result, message="已退回")
