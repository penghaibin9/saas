"""学生 PC 门户岗位实习合规、知情与安全教育接口。

与学生小程序复用同一业务服务，不复制状态机。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from app.core.response import success
from app.core.security import get_current_user
from app.modules.internship.services import internship_consent_service as consent
from app.modules.internship.services import internship_safety_service as safety
from app.modules.internship.services import internship_student_compliance_service as compliance
from app.api.v1.mobile_internship_student import my_safety_course_detail

router = APIRouter(prefix="/portal/internship", tags=["学生PC门户-岗位实习合规"])


@router.get("/compliance", summary="本人岗位实习权威合规状态")
def portal_compliance(
    operation: str = Query(default="ONBOARD"),
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(compliance.evaluate_my(user, operation=operation, batch_id=batchId))


@router.get("/consents", summary="本人知情确认任务")
def portal_consents(user=Depends(get_current_user)):
    return success(consent.list_my(user))


@router.get("/consents/{consent_id}", summary="本人知情确认正文")
def portal_consent_detail(consent_id: str, user=Depends(get_current_user)):
    return success(consent.get_my(consent_id, user))


@router.post("/consents/{consent_id}/view", summary="本人标记已阅读知情书")
def portal_consent_view(consent_id: str, user=Depends(get_current_user)):
    return success(consent.mark_viewed(consent_id, user))


@router.post("/consents/{consent_id}/confirm", summary="本人确认知情书")
def portal_consent_confirm(
    consent_id: str,
    request: Request,
    body: dict = Body(default={}),
    user=Depends(get_current_user),
):
    return success(consent.confirm(
        consent_id, body or {}, user, request.client.host if request.client else None))


@router.post("/consents/{consent_id}/reject", summary="本人拒绝知情书")
def portal_consent_reject(
    consent_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(consent.reject(consent_id, body or {}, user))


@router.get("/safety/courses", summary="本人当前批次安全教育课程")
def portal_safety_courses(user=Depends(get_current_user)):
    return success(safety.list_my_courses(user))


@router.get("/safety/completions", summary="本人安全教育完成记录")
def portal_safety_completions(user=Depends(get_current_user)):
    return success(safety.list_my_completions(user))


@router.get("/safety/courses/{course_id}/detail", summary="本人安全教育课程详情")
def portal_safety_detail(course_id: str, user=Depends(get_current_user)):
    # 复用移动端详情装配逻辑，返回结构保持四端一致。
    return my_safety_course_detail(course_id, user)


@router.post("/safety/courses/{course_id}/start", summary="开始本人安全课程")
def portal_safety_start(course_id: str, user=Depends(get_current_user)):
    return success(safety.start_my_course(course_id, user))


@router.post("/safety/courses/{course_id}/submit", summary="提交本人安全课程学习结果")
def portal_safety_submit(
    course_id: str,
    body: dict = Body(default={}),
    user=Depends(get_current_user),
):
    return success(safety.submit_my_course(course_id, body or {}, user))


@router.post("/safety/completions/{completion_id}/commit", summary="确认本人安全承诺")
def portal_safety_commit(
    completion_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(safety.commit_my_completion(completion_id, body or {}, user))
