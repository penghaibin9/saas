"""学生小程序岗位实习本人权威接口。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, Query

from app.api.v1.file_contract import validated_local_file_response
from app.core.permissions import require_module
from app.core.response import success
from app.core.security import get_current_user
from app.modules.internship.services import internship_agreement_service as agreements
from app.modules.internship.services import internship_plan_service as plans
from app.modules.internship.services import internship_plan_task_service as plan_tasks
from app.modules.internship.services import internship_safety_service as safety
from app.modules.internship.services import internship_student_application_context_service as applications
from app.modules.internship.services import internship_student_change_context_service as changes
from app.modules.internship.services import internship_student_compliance_service as compliance
from app.modules.internship.services import internship_student_consent_context_service as consent_context
from app.modules.internship.services import internship_student_dashboard_service as dashboard
from app.modules.internship.services import internship_student_leave_context_service as leaves
from app.modules.internship.services import internship_student_makeup_context_service as makeups
from app.modules.internship.services import internship_student_report_context_service as reports
from app.modules.internship.services import internship_student_notice_service as student_notices
from app.modules.internship.services import internship_student_eval_service as student_evals
from app.modules.internship.services import internship_student_checkin_service as checkins
from app.modules.internship.services import internship_checkin_exemption_service as checkin_exemptions
from app.modules.internship.services import internship_material_requirement_service as material_requirements
from app.modules.internship.services import internship_rotation_service as rotations
from app.modules.internship.services import internship_payroll_service as payrolls
from app.modules.internship.services import internship_score_appeal_service as score_appeals
from app.modules.internship.services import internship_teacher_activity_service as teacher_activity
from app.modules.internship.services import internship_risk_service as risks
from app.modules.internship.services.internship_student_context_guard import (
    require_context_fields,
)

router = APIRouter(
    prefix="/mobile/internship",
    tags=["学生移动端-岗位实习权威状态"],
    dependencies=[Depends(require_module("internship"))],
)


def _selected_checkin_batch(
    header_value: str | None = Header(default=None, alias="X-Internship-Batch-Id"),
    explicit: int | None = Query(default=None, alias="batchId", ge=1),
):
    return str(explicit) if explicit is not None else header_value


@router.get("/context/my", summary="本人所选批次岗位实习工作台")
def my_selected_dashboard(
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(dashboard.get_my_dashboard(user, batch_id=batchId))


@router.get("/emergency-notices", summary="本人当前批次持久紧急通知")
def my_emergency_notices(
    batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(teacher_activity.list_student_notices(user, batch_id=batchId))


@router.get("/emergency-notices/pending", summary="本人当前批次待强弹确认紧急通知")
def my_pending_emergency_notices(
    batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(student_notices.pending_notices(user, batch_id=batchId))


@router.post("/emergency-notices/{notice_id}/ack", summary="本人明确确认紧急通知已知悉")
def acknowledge_emergency_notice(
    notice_id: int,
    batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(
        student_notices.acknowledge_notice(
            user,
            notice_id=notice_id,
            batch_id=batchId,
        ),
        message="已记录知悉回执",
    )


@router.get("/compliance/my", summary="本人岗位实习权威合规状态与下一步")
def my_compliance(
    operation: str = Query(default="ONBOARD"),
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(compliance.evaluate_my(user, operation=operation, batch_id=batchId))


@router.post("/checkin/preflight", summary="本人签到预检、当地日期与短时定位凭证")
def my_checkin_preflight(
    timezoneName: str | None = Query(default=None),
    batch_id=Depends(_selected_checkin_batch),
    user=Depends(get_current_user),
):
    return success(checkins.preflight(
        user, batch_id=batch_id, timezone_name=timezoneName))


@router.post("/checkin", summary="本人现场签到（服务端水印照片 + 定位核验）")
def my_checkin(
    body: dict = Body(default={}),
    batch_id=Depends(_selected_checkin_batch),
    user=Depends(get_current_user),
):
    return success(checkins.checkin(user, body or {}, batch_id=batch_id))


@router.get("/checkin/week", summary="本人本周签到兼容视图")
def my_checkin_week(
    timezoneName: str | None = Query(default=None),
    batch_id=Depends(_selected_checkin_batch),
    user=Depends(get_current_user),
):
    return success(checkins.week(
        user, batch_id=batch_id, timezone_name=timezoneName))


@router.get("/checkin/calendar", summary="本人完整月度签到日历")
def my_checkin_calendar(
    month: str | None = Query(default=None),
    timezoneName: str | None = Query(default=None),
    batch_id=Depends(_selected_checkin_batch),
    user=Depends(get_current_user),
):
    return success(checkins.calendar(
        user, month=month, batch_id=batch_id, timezone_name=timezoneName))


@router.get("/context/checkin-exemptions", summary="本人当前批次免签申请")
def my_checkin_exemptions(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(checkin_exemptions.list_my(
        user, batch_id=batchId, internship_id=internshipId))


@router.post("/context/checkin-exemptions", summary="本人申请一段日期免签")
def apply_checkin_exemption(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(checkin_exemptions.apply(user, body or {}), message="免签申请已提交")


@router.post("/context/checkin-exemptions/{exemption_id}/withdraw", summary="撤回本人待审核免签申请")
def withdraw_checkin_exemption(
    exemption_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(checkin_exemptions.withdraw(
        user, exemption_id, body or {}), message="免签申请已撤回")


@router.get("/context/rotations", summary="本人当前实习轮岗记录")
def my_rotations(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(rotations.list_my(
        user, batch_id=batchId, internship_id=internshipId))


@router.post("/context/rotations/{rotation_id}/self-evaluation", summary="本人提交轮岗自评")
def my_rotation_self_evaluation(
    rotation_id: int,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(rotations.submit_self_evaluation(
        rotation_id, body or {}, user), message="轮岗自评已提交")


@router.get("/context/payroll", summary="本人月度工资单与历史版本")
def my_payroll(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(payrolls.list_my(
        user, batch_id=batchId, internship_id=internshipId))


@router.post("/context/payroll", summary="本人提交或更正月度工资单")
def my_payroll_submit(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(payrolls.submit_my(user, body or {}), message="工资单已提交审核")


@router.get("/context/material-requirements", summary="本人当前批次材料收件要求")
def my_material_requirements(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(material_requirements.list_my_requirements(
        user, batch_id=batchId, internship_id=internshipId))


@router.post("/context/material-requirements/{requirement_id}/submit", summary="提交或退回后重交材料")
def my_material_requirement_submit(
    requirement_id: int,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(material_requirements.submit_material(
        user, requirement_id, body or {}), message="材料已提交审核")


@router.get("/context/material-requirements/{requirement_id}/template/download", summary="下载适用于本人的材料模板")
def my_material_template_download(
    requirement_id: int,
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    path, filename = material_requirements.template_download(
        requirement_id, user, batch_id=batchId, internship_id=internshipId)
    return validated_local_file_response(
        path,
        filename=filename,
        audit_action="INTERNSHIP_STUDENT_MATERIAL_TEMPLATE_DOWNLOAD",
        audit_target=f"internship-material-requirement:{requirement_id}",
        audit_detail={
            "requirementId": str(requirement_id),
            "batchId": str(batchId),
            "internshipId": str(internshipId),
            "surface": "STUDENT_MINI",
        },
    )


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
def my_selected_applications(
    batchId: int | None = Query(default=None, ge=1),
    internshipId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    return success(applications.list_my(
        user, batch_id=batchId, internship_id=internshipId))


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
        user, application_id, body or {}),
        message="申请已提交审核")


@router.post("/context/applications/{application_id}/withdraw", summary="按版本撤回本人待审核申请")
def withdraw_selected_application(
    application_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(applications.withdraw(
        user, application_id, body or {}),
        message="申请已撤回")


@router.get("/context/leaves", summary="本人所选批次实习请假列表")
def my_selected_leaves(
    batchId: int | None = Query(default=None, ge=1),
    internshipId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    return success(leaves.list_my(
        user, batch_id=batchId, internship_id=internshipId))


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
        user, leave_id, body or {}), message="请假已撤回")


@router.post("/context/leaves/{leave_id}/return", summary="按版本办理本人销假")
def return_selected_leave(
    leave_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(leaves.return_my(user, leave_id, body or {}), message="销假已提交")


@router.get("/context/makeups", summary="本人所选批次补卡申请列表")
def my_selected_makeups(
    batchId: int | None = Query(default=None, ge=1),
    internshipId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    return success(makeups.list_my(
        user, batch_id=batchId, internship_id=internshipId))


@router.post("/context/makeups", summary="本人发起合规补卡申请")
def apply_selected_makeup(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(makeups.apply(user, body or {}), message="补卡申请已提交")


@router.post("/context/makeups/{makeup_id}/withdraw", summary="按版本撤回本人待审核补卡")
def withdraw_selected_makeup(
    makeup_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(makeups.withdraw(
        user, makeup_id, body or {}), message="补卡已撤回")


@router.get("/context/plan", summary="本人当前已发布实习计划及回执版本")
def my_selected_plan(user=Depends(get_current_user)):
    return success(plans.student_my_plan(user))


@router.post("/context/plan/acknowledge", summary="按正文与回执版本确认实习计划")
def acknowledge_selected_plan(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    require_context_fields(body or {})
    return success(plans.student_acknowledge(user, body or {}), message="已确认当前版本实习计划")


@router.get("/context/plan/tasks", summary="本人当前计划任务与进度版本")
def my_selected_plan_tasks(user=Depends(get_current_user)):
    return success(plan_tasks.student_tasks(user))


@router.post("/context/plan/tasks/{sort_order}/submit", summary="按版本提交当前计划任务完成情况")
def submit_selected_plan_task(
    sort_order: int,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(
        plan_tasks.student_submit_task(user, sort_order, body or {}),
        message="任务已提交，等待指导教师确认",
    )


@router.get("/context/agreements", summary="本人所选批次三方协议列表")
def my_selected_agreements(user=Depends(get_current_user)):
    return success(agreements.my_agreements(user))


@router.get("/context/agreements/{agreement_id}", summary="本人三方协议详情与当前版本")
def my_selected_agreement_detail(
    agreement_id: str,
    user=Depends(get_current_user),
):
    return success(agreements.get_student_agreement(user, agreement_id))


@router.post("/context/agreements/{agreement_id}/confirm", summary="按版本确认或驳回本人三方协议")
def confirm_selected_agreement(
    agreement_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    payload = body or {}
    require_context_fields(payload)
    return success(agreements.student_confirm(
        user, agreement_id, str(payload.get("action") or "").upper(),
        payload.get("reason") or "", body=payload), message="协议办理完成")


@router.get("/context/changes", summary="本人当前批次调岗、换单位与退岗申请")
def my_selected_changes(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(changes.list_my(
        user, batch_id=batchId, internship_id=internshipId))


@router.get("/context/changes/target-positions", summary="本人当前批次可申请的真实目标岗位")
def my_change_target_positions(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    changeType: str = Query(default="CHANGE_POSITION"),
    keyword: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=50),
    user=Depends(get_current_user),
):
    return success(changes.list_target_positions(
        user, batch_id=batchId, internship_id=internshipId,
        keyword=keyword, change_type=changeType, page=page, page_size=pageSize))


@router.post("/context/changes", summary="按当前批次和版本发起实习变更")
def apply_selected_change(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(changes.apply(user, body or {}), message="变更申请已提交")


@router.post("/context/changes/{change_id}/withdraw", summary="按当前批次和版本撤回实习变更")
def withdraw_selected_change(
    change_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(
        changes.withdraw(user, change_id, body or {}),
        message="变更申请已撤回",
    )


@router.get("/context/reports", summary="本人当前批次月报与实习总结")
def my_selected_reports(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(reports.list_my(
        user, batch_id=batchId, internship_id=internshipId))


@router.post("/context/reports", summary="按当前批次和版本提交月报或实习总结")
def submit_selected_report(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(reports.submit(user, body or {}), message="过程报告已提交")


@router.get("/context/weekly-reports", summary="本人当前批次周报")
def my_selected_weekly_reports(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=50),
    focusReportId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    return success(reports.list_weekly(
        user,
        batch_id=batchId,
        internship_id=internshipId,
        page=page,
        page_size=pageSize,
        focus_report_id=focusReportId,
    ))


@router.post("/context/weekly-reports", summary="按当前批次和版本提交周报")
def submit_selected_weekly_report(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(
        reports.submit_weekly(user, body or {}),
        message="周报已提交",
    )


@router.get("/context/self-eval", summary="本人当前批次实习自评")
def my_selected_self_eval(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(student_evals.my_eval(
        user, batch_id=batchId, internship_id=internshipId))


@router.post("/context/self-eval", summary="按当前批次和版本提交实习自评")
def submit_selected_self_eval(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    require_context_fields(body or {})
    return success(
        student_evals.student_submit(user, body or {}),
        message="实习自评已提交",
    )


@router.get("/context/score-appeal", summary="本人当前实习成绩与最近申诉")
def my_selected_score_appeal(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(score_appeals.my_latest(
        user, batch_id=batchId, internship_id=internshipId))


@router.post("/context/score-appeal", summary="本人对当前实习成绩发起申诉")
def submit_selected_score_appeal(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    require_context_fields(body or {})
    return success(score_appeals.create(user, body or {}), message="成绩申诉已提交")


@router.post("/context/help", summary="本人在当前实习记录发起求助")
def submit_selected_help(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    require_context_fields(body or {})
    return success(risks.student_help_report(user, body or {}), message="求助已提交")


@router.get("/context/help", summary="本人查看当前实习求助处置进度")
def my_selected_help(
    batchId: int = Query(..., ge=1),
    internshipId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(risks.my_student_help(
        user, batch_id=batchId, internship_id=internshipId))
