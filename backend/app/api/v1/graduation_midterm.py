"""毕业设计中心 · 中期检查 API（/api/v1/graduation/gd-midterms/*）。

独立 router；静态子路由（stats）在 /{gd_student_id} 之前声明。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.graduation_midterm import MidtermCheckRequest, MidtermRectifyReview, MidtermRectifySubmit
from app.services import audit_log
from app.services import graduation_midterm_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-中期检查"])


@router.get("/gd-midterms/stats", summary="中期检查统计")
def gd_midterm_stats(user=Depends(get_current_user)):
    return success(svc.midterm_stats())


@router.get("/gd-midterms", summary="中期检查列表（分页+筛选）")
def gd_midterms(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               keyword: Optional[str] = None, status: Optional[str] = None,
               user=Depends(get_current_user)):
    items, total = svc.list_midterms(page, pageSize, keyword=keyword, status=status)
    return success(paginate(items, total, page, pageSize))


@router.get("/gd-midterms/{gd_student_id}", summary="按学生查中期检查记录（不存在则创建待检查态）")
def gd_midterm_detail(gd_student_id: str, user=Depends(get_current_user)):
    return success(svc.get_midterm(gd_student_id))


@router.post("/gd-midterms/{gd_student_id}/check", summary="中期检查（三档结论：PASS/RECTIFY/FAIL）")
def gd_midterm_check(gd_student_id: str, body: MidtermCheckRequest, user=Depends(get_current_user)):
    result = svc.conduct_check(gd_student_id, body.conclusion, body.comment, body.rectifyDeadline)
    audit_log.record("中期检查", f"graduation-midterm:{gd_student_id}", detail={"conclusion": body.conclusion})
    return success(result, message="已提交检查结论")


@router.post("/gd-midterms/{gd_student_id}/rectify", summary="学生提交整改")
def gd_midterm_rectify_submit(gd_student_id: str, body: MidtermRectifySubmit, user=Depends(get_current_user)):
    result = svc.submit_rectification(gd_student_id, body.content)
    audit_log.record("提交中期整改", f"graduation-midterm:{gd_student_id}")
    return success(result, message="已提交整改")


@router.post("/gd-midterms/{gd_student_id}/rectify/review", summary="教师复核整改（PASS/FAIL）")
def gd_midterm_rectify_review(gd_student_id: str, body: MidtermRectifyReview, user=Depends(get_current_user)):
    result = svc.review_rectification(gd_student_id, body.action, body.comment)
    audit_log.record("复核中期整改", f"graduation-midterm:{gd_student_id}", detail={"action": body.action})
    return success(result, message="已复核")
