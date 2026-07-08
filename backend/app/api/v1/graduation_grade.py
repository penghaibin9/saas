"""毕业设计中心 · 成绩评定 API（/api/v1/graduation/gd-grades/*）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.graduation_grade import GradeCalculateRequest, GradeReviewRequest, GradeWithdrawRequest
from app.services import audit_log
from app.services import graduation_grade_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-成绩评定"])


@router.get("/gd-grades/stats", summary="成绩统计")
def gd_grade_stats(user=Depends(get_current_user)):
    return success(svc.grade_stats())


@router.get("/gd-grades", summary="成绩列表（分页+筛选）")
def gd_grades(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, status: Optional[str] = None,
             user=Depends(get_current_user)):
    items, total = svc.list_grades(page, pageSize, keyword=keyword, status=status)
    return success(paginate(items, total, page, pageSize))


@router.get("/gd-grades/{gd_student_id}", summary="按学生查成绩（不存在则创建待核算态）")
def gd_grade_detail(gd_student_id: str, user=Depends(get_current_user)):
    return success(svc.get_grade(gd_student_id))


@router.post("/gd-grades/{gd_student_id}/calculate", summary="核算成绩（按批次权重计算综合分）")
def gd_grade_calculate(gd_student_id: str, body: GradeCalculateRequest, user=Depends(get_current_user)):
    result = svc.calculate_grade(gd_student_id, body.advisorScore, body.reviewerScore, body.defenseScore)
    audit_log.record("核算成绩", f"graduation-grade:{gd_student_id}")
    return success(result, message="已核算")


@router.post("/gd-grades/{gd_student_id}/review", summary="复核成绩（APPROVE/RETURN）")
def gd_grade_review(gd_student_id: str, body: GradeReviewRequest, user=Depends(get_current_user)):
    result = svc.review_grade(gd_student_id, body.action, body.comment)
    audit_log.record("复核成绩", f"graduation-grade:{gd_student_id}", detail={"action": body.action})
    return success(result, message="已复核")


@router.post("/gd-grades/{gd_student_id}/publish", summary="发布成绩（须复核通过）")
def gd_grade_publish(gd_student_id: str, user=Depends(get_current_user)):
    result = svc.publish_grade(gd_student_id)
    audit_log.record("发布成绩", f"graduation-grade:{gd_student_id}")
    return success(result, message="已发布")


@router.post("/gd-grades/{gd_student_id}/withdraw", summary="撤回已发布成绩（原因≥5字）")
def gd_grade_withdraw(gd_student_id: str, body: GradeWithdrawRequest, user=Depends(get_current_user)):
    result = svc.withdraw_grade(gd_student_id, body.reason)
    audit_log.record("撤回成绩", f"graduation-grade:{gd_student_id}", detail={"reason": body.reason})
    return success(result, message="已撤回")
