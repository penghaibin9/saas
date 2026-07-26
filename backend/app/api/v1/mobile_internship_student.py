"""学生小程序岗位实习本人权威接口。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_module
from app.core.response import success
from app.core.security import get_current_user
from app.modules.internship.services import internship_safety_service as safety
from app.modules.internship.services import internship_student_application_context_service as applications
from app.modules.internship.services import internship_student_compliance_service as compliance
from app.modules.internship.services import internship_student_consent_context_service as consent_context
from app.modules.internship.services import internship_student_dashboard_service as dashboard
from app.modules.internship.services import internship_student_leave_context_service as leaves

router = APIRouter(
    prefix="/mobile/internship",
    tags=["学生移动端-岗位实习权威状态"],
    dependencies=[Depends(require_module("internship"))],
)


@router.get("/context/my", summary="本人所选批次岗位实习工作台")
def my_selected_dashboard(
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(dashboard.get_my_dashboard(user, batch_id=batchId))


@router.get("/compliance/my", summary="本人岗位实习权威合规状态与下一步")
def my_compliance(
    operation: str = Query(default="ONBOARD"),
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(compliance.evaluate_my(user, operation=operation, batch_id=batchId))


@router.get("/context/consents", summary="本人所选批次知情确认任务")
def my_selected_consents(
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(consent_context.list_my(user, batch_id=batchId))


@router.get("/context/safety/courses", summary="本人所选批次安全教育课程")
def my_selected_safety_courses(
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(safety.list_my_courses(user, batch_id=batchId))


@router.get("/context/safety/completions", summary="本人所选批次安全教育完成记录")
def my_selected_safety_completions(
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(safety.list_my_completions(user, batch_id=batchId))


@router.get("/safety/courses/{course_id}/detail", summary="本人安全教育课程详情与完成版本")
def my_safety_course_detail(course_id: str, user=Depends(get_current_user)):
    return success(safety.get_my_course_detail(course_id, user))


@router.get("/context/applications", summary="本人所选批次正式实习申请")
def my_selected_applications(user=Depends(get_current_user)):
    return success(applications.list_my(user))


@router.put("/context/applications", summary="按版本保存本人正式实习申请草稿")
def save_selected_application(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(applications.save(user, body or {}), message="申请草稿已保存")


@router.post("/context/applications/{application_id}/submit", summary="按版本提交本人正式实习申请")
def submit_selected_application(
    application_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(applications.submit(
        user, application_id, (body or {}).get("expectedVersion")),
        message="申请已提交审核")


@router.post("/context/applications/{application_id}/withdraw", summary="按版本撤回本人待审核申请")
def withdraw_selected_application(
    application_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(applications.withdraw(
        user, application_id, (body or {}).get("expectedVersion")),
        message="申请已撤回")


@router.get("/context/leaves", summary="本人所选批次实习请假列表")
def my_selected_leaves(user=Depends(get_current_user)):
    return success(leaves.list_my(user))


@router.post("/context/leaves", summary="本人发起实习请假")
def apply_selected_leave(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(leaves.apply(user, body or {}), message="请假申请已提交")


@router.post("/context/leaves/{leave_id}/withdraw", summary="按版本撤回本人待审批请假")
def withdraw_selected_leave(
    leave_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(leaves.withdraw(
        user, leave_id, (body or {}).get("expectedVersion")), message="请假已撤回")


@router.post("/context/leaves/{leave_id}/return", summary="按版本办理本人销假")
def return_selected_leave(
    leave_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(leaves.return_my(user, leave_id, body or {}), message="销假已提交")
