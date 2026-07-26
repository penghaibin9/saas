"""学生 PC 门户岗位实习权威接口。

与学生小程序复用同一业务服务，不复制状态机；批次由显式 batchId 或统一
X-Internship-Batch-Id 上下文解析。正式申请、请假撤回与销假均强制乐观锁版本。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from app.core.response import success
from app.core.security import get_current_user
from app.modules.internship.services import internship_consent_service as consent
from app.modules.internship.services import internship_safety_service as safety
from app.modules.internship.services import internship_student_application_context_service as applications
from app.modules.internship.services import internship_student_compliance_service as compliance
from app.modules.internship.services import internship_student_consent_context_service as consent_context
from app.modules.internship.services import internship_student_leave_context_service as leaves

router = APIRouter(prefix="/portal/internship", tags=["学生PC门户-岗位实习权威接口"])


@router.get("/compliance", summary="本人岗位实习权威合规状态")
def portal_compliance(
    operation: str = Query(default="ONBOARD"),
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(compliance.evaluate_my(user, operation=operation, batch_id=batchId))


@router.get("/consents", summary="本人所选批次知情确认任务")
def portal_consents(
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(consent_context.list_my(user, batch_id=batchId))


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


@router.get("/safety/courses", summary="本人所选批次安全教育课程")
def portal_safety_courses(
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(safety.list_my_courses(user, batch_id=batchId))


@router.get("/safety/completions", summary="本人所选批次安全教育完成记录")
def portal_safety_completions(
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(safety.list_my_completions(user, batch_id=batchId))


@router.get("/safety/courses/{course_id}/detail", summary="本人安全教育课程详情")
def portal_safety_detail(course_id: str, user=Depends(get_current_user)):
    return success(safety.get_my_course_detail(course_id, user))


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


@router.get("/context/applications", summary="本人所选批次正式实习申请")
def portal_application_list(user=Depends(get_current_user)):
    return success(applications.list_my(user))


@router.put("/context/applications", summary="按版本保存本人正式实习申请草稿")
def portal_application_save(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(applications.save(user, body or {}), message="申请草稿已保存")


@router.post("/context/applications/{application_id}/submit", summary="按版本提交本人正式实习申请")
def portal_application_submit(
    application_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(
        applications.submit(user, application_id, (body or {}).get("expectedVersion")),
        message="申请已提交审核",
    )


@router.post("/context/applications/{application_id}/withdraw", summary="按版本撤回本人待审核申请")
def portal_application_withdraw(
    application_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(
        applications.withdraw(user, application_id, (body or {}).get("expectedVersion")),
        message="申请已撤回",
    )


@router.get("/context/leaves", summary="本人所选批次实习请假列表")
def portal_leave_list(user=Depends(get_current_user)):
    return success(leaves.list_my(user))


@router.post("/context/leaves", summary="本人发起实习请假")
def portal_leave_apply(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(leaves.apply(user, body or {}), message="请假申请已提交")


@router.post("/context/leaves/{leave_id}/withdraw", summary="按版本撤回本人待审批请假")
def portal_leave_withdraw(
    leave_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(leaves.withdraw(
        user, leave_id, (body or {}).get("expectedVersion")), message="请假已撤回")


@router.post("/context/leaves/{leave_id}/return", summary="按版本办理本人销假")
def portal_leave_return(
    leave_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(leaves.return_my(user, leave_id, body or {}), message="销假已提交")
