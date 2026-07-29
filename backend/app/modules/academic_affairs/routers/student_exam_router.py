"""学生考试安排与缓考申请安全路由（四端重构兼容入口）。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.security import get_current_user
from app.core.response import success
from app.modules.academic_affairs.services import student_exam_read_service as service

router = APIRouter(prefix="/mobile/academic/exam-v2", tags=["academic-affairs-student-exam"])


@router.get("/my", summary="学生本人考试安排（学校时区 + FINISHED 可见）")
def exam_my(user=Depends(get_current_user)):
    return success(service.exam_my(user))


@router.get("/defer-options", summary="学生本人可申请缓考课程（名单归属 + 本地开考判断）")
def defer_options(user=Depends(get_current_user)):
    return success(service.deferrable_courses(user))


@router.post("/defer/apply", summary="学生本人申请缓考（防猜考试课程ID）")
def defer_apply(body: dict = Body(...), user=Depends(get_current_user)):
    return success(service.defer_apply(user, body), message="缓考申请已提交")
