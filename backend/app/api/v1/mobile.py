"""移动端聚合 API（/api/v1/mobile/*）。
学生端：只返回本人跨域数据（userType 必须 STUDENT，否则 403）。
教师端：本校待办/待处理（严格租户过滤），只读。
除 /orientation/batch-status（登录页迎新入口倒计时，登录前必须可查，不含个人数据）外，
所有接口鉴权；查不到本人档案返回空态（hasData=false），不 500。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Path

from app.core.permissions import require_module, require_permission
from app.core.response import success
from app.core.security import get_current_user
from app.modules.internship.services import internship_makeup_service as mk
from app.modules.academic_affairs.services import mobile_academic_affairs_service as aa
from app.services import affairs_activity_service as activity_svc
from app.services import mobile_affairs_service as aff
from app.services import mobile_student_service as stu
from app.services import mobile_teacher_service as tea

router = APIRouter(prefix="/mobile", tags=["移动端聚合"])

# 毕设学生端子路由：与 PC 管理端同一模块授权开关，未授权租户即使绕过前端隐藏直调接口也 403。
gd = APIRouter(prefix="/graduation", tags=["移动端聚合"],
               dependencies=[Depends(require_module("module.graduationDesign.enabled"))])


# ── 学生端·我的 ──
@router.get("/me/overview", summary="学生首页总览（本人）")
def me_overview(user=Depends(get_current_user)):
    return success(stu.me_overview(user))


@router.get("/home", summary="学生首页聚合（总览+迎新+批次，一次鉴权）")
def student_home(user=Depends(get_current_user)):
    return success(stu.home(user))


@router.get("/me/todos", summary="我的待办（本人）")
def me_todos(user=Depends(get_current_user)):
    return success(stu.my_todos(user))


@router.get("/me/messages", summary="我的消息（本人）")
def me_messages(user=Depends(get_current_user)):
    return success(stu.my_messages(user))


@router.get("/me/profile", summary="我的档案（本人·脱敏）")
def me_profile(user=Depends(get_current_user)):
    return success(stu.my_profile(user))


# ── 学生·心理健康自评（移动端首创，系统不做任何自动诊断，仅登记原始作答+算术汇总分）──
@router.get("/me/psy-survey/questions", summary="心理健康自评·题目")
def psy_survey_questions(user=Depends(get_current_user)):
    return success(stu.psy_survey_questions(user))


@router.post("/me/psy-survey/submit", summary="心理健康自评·提交（命中阈值/主动求助自动登记人工关注）")
def psy_survey_submit(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.psy_survey_submit(user, body), message="已提交")


@router.get("/me/psy-survey/history", summary="心理健康自评·本人历史记录")
def psy_survey_history(user=Depends(get_current_user)):
    return success(stu.psy_survey_history(user))


# ── 学生·消息通知设置（移动端首创，真实过滤 me/messages 聚合，非假开关）──
@router.get("/me/notify-preferences", summary="我的消息通知分类开关")
def me_notify_preferences(user=Depends(get_current_user)):
    return success(stu.notify_preferences(user))


@router.post("/me/notify-preferences", summary="设置消息通知分类开关")
def me_notify_set_preference(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.notify_set_preference(user, body), message="已保存")


@router.get("/me/applications", summary="我的申请（本人聚合）")
def me_applications(user=Depends(get_current_user)):
    return success(stu.my_applications(user))


@router.get("/me/portal-config", summary="学生 PC 门户配置（仅学生·本人所在租户）")
def me_portal_config(user=Depends(get_current_user)):
    """学生 PC 门户启动配置。仅 STUDENT 可访问（非学生 403）；只返回本人租户配置，
    不接受 tenantId 查询参数，杜绝跨租户读取；配置缺失返回安全默认，不 500。"""
    from app.core.context import current_tenant_id
    from app.core.exceptions import no_permission
    from app.services import student_portal_service as sp
    if (user.get("userType") or "").strip().upper() != "STUDENT":
        raise no_permission("学生 PC 门户仅学生可访问，请使用学生账号登录")
    return success(sp.get_config(int(current_tenant_id() or 0)))


@router.post("/campus-service/apply", summary="提交在校服务申请（本人）")
def campus_service_apply(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.campus_service_apply(user, body))


@router.post("/internship/weekly", summary="提交实习周报（本人）")
def internship_weekly(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.internship_weekly_submit(user, body))


@router.post("/internship/checkin", summary="实习每日打卡（本人，一天一次，真实落库）")
def internship_checkin(body: dict = Body(default={}), user=Depends(get_current_user)):
    return success(stu.internship_checkin(user, body))


@router.get("/internship/checkin/week", summary="本周打卡记录（本人）")
def internship_checkin_week(user=Depends(get_current_user)):
    return success(stu.internship_checkin_week(user))


@router.get("/internship/enterprises", summary="企业岗位库（本人可浏览，城市筛选）")
def internship_enterprises(city: str = "", user=Depends(get_current_user)):
    return success(stu.internship_enterprises(user, city))


@router.post("/internship/exceptions/{exception_id}/appeal", summary="本人对未处理打卡异常提交凭证申诉")
def internship_exception_appeal(exception_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.internship_exception_appeal(user, exception_id, body), message="申诉已提交")


@router.post("/internship/makeup", summary="补卡申请（本人某日缺卡，待指导教师审批）")
def internship_makeup_apply(body: dict = Body(...), user=Depends(get_current_user)):
    b = body or {}
    return success(mk.apply(user, checkin_date=b.get("checkinDate") or b.get("date") or "",
                            reason=b.get("reason") or "", makeup_type=b.get("makeupType") or "MISSING"),
                   message="补卡申请已提交")


@router.post("/internship/makeup/{makeup_id}/withdraw", summary="撤回本人补卡申请")
def internship_makeup_withdraw(makeup_id: str, user=Depends(get_current_user)):
    return success(mk.withdraw(user, makeup_id), message="已撤回")


@router.get("/internship/leaves", summary="本人实习请假列表")
def internship_my_leaves(user=Depends(get_current_user)):
    from app.modules.internship.services import internship_leave_service as lv
    return success(lv.my_leaves(user))


@router.post("/internship/leave", summary="实习请假申请（本人，待指导教师审批）")
def internship_leave_apply(body: dict = Body(...), user=Depends(get_current_user)):
    from app.modules.internship.services import internship_leave_service as lv
    return success(lv.apply(user, body or {}), message="请假申请已提交")


@router.post("/internship/leave/{leave_id}/withdraw", summary="撤回本人请假申请")
def internship_leave_withdraw(leave_id: str, user=Depends(get_current_user)):
    from app.modules.internship.services import internship_leave_service as lv
    return success(lv.withdraw(user, leave_id), message="已撤回")


@router.post("/internship/leave/{leave_id}/return", summary="本人实习请假销假")
def internship_leave_return(leave_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    from app.modules.internship.services import internship_leave_service as lv
    return success(lv.return_my(user, leave_id, body or {}), message="销假已登记")


@router.get("/internship/agreements", summary="本人三方协议列表")
def internship_my_agreements(user=Depends(get_current_user)):
    from app.modules.internship.services import internship_agreement_service as agr
    return success(agr.my_agreements(user))


@router.get("/internship/agreements/{agreement_id}", summary="本人三方协议详情（含渲染正文）")
def internship_agreement_detail(agreement_id: str, user=Depends(get_current_user)):
    from app.modules.internship.services import internship_agreement_service as agr
    return success(agr.get_student_agreement(user, agreement_id))


@router.post("/internship/agreements/{agreement_id}/confirm", summary="本人确认/驳回三方协议")
def internship_agreement_confirm(agreement_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    from app.modules.internship.services import internship_agreement_service as agr
    b = body or {}
    return success(agr.student_confirm(user, agreement_id, (b.get("action") or "").upper(),
                                       b.get("reason") or ""), message="已提交")


@router.get("/internship/self-eval", summary="本人实习自评/鉴定")
def internship_my_self_eval(user=Depends(get_current_user)):
    from app.modules.internship.services import internship_student_eval_service as se
    return success(se.my_eval(user))


@router.post("/internship/self-eval", summary="提交/重交本人实习自评（总结/收获/问题）")
def internship_submit_self_eval(body: dict = Body(...), user=Depends(get_current_user)):
    from app.modules.internship.services import internship_student_eval_service as se
    return success(se.student_submit(user, body or {}), message="自评已提交")


@router.get("/internship/intention", summary="本人实习意向（含可选岗位列表）")
def internship_intention_my(user=Depends(get_current_user)):
    return success(stu.internship_intention_my(user))


@router.put("/internship/intention", summary="保存本人实习意向（草稿）")
def internship_intention_save(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.internship_intention_save(user, body or {}), message="意向已保存")


@router.post("/internship/intention/submit", summary="提交本人实习意向")
def internship_intention_submit(user=Depends(get_current_user)):
    return success(stu.internship_intention_submit(user), message="意向已提交")


@router.post("/internship/intention/withdraw", summary="撤回本人实习意向")
def internship_intention_withdraw(user=Depends(get_current_user)):
    return success(stu.internship_intention_withdraw(user), message="意向已撤回")


@router.get("/internship/applications", summary="本人正式实习申请列表")
def internship_application_list(user=Depends(get_current_user)):
    return success(stu.internship_application_list(user))


@router.put("/internship/applications", summary="保存本人正式实习申请草稿")
def internship_application_save(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.internship_application_save(user, body or {}), message="申请草稿已保存")


@router.post("/internship/applications/{application_id}/submit", summary="提交本人正式实习申请")
def internship_application_submit(application_id: str, user=Depends(get_current_user)):
    return success(stu.internship_application_submit(user, application_id), message="申请已提交审核")


@router.post("/internship/applications/{application_id}/withdraw", summary="撤回本人待审核实习申请")
def internship_application_withdraw(application_id: str, user=Depends(get_current_user)):
    return success(stu.internship_application_withdraw(user, application_id), message="申请已撤回")


@router.post("/internship/process-report", summary="提交日报/月报/实习总结（本人）")
def internship_process_report(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.internship_process_report_submit(user, body or {}))


@router.get("/internship/process-reports", summary="本人日报/月报/实习总结列表（含批阅意见）")
def internship_my_process_reports(user=Depends(get_current_user)):
    from app.modules.internship.services import internship_process_report_service as pr
    return success(pr.my_reports(user))


@router.get("/internship/change-requests", summary="本人实习变更申请列表")
def internship_my_change_requests(user=Depends(get_current_user)):
    return success(stu.internship_change_list(user))


@router.post("/internship/change-request", summary="发起实习变更申请（换岗/换单位/自主实习）")
def internship_change_apply(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.internship_change_apply(user, body or {}), message="变更申请已提交")


@router.post("/internship/change-request/{change_id}/withdraw", summary="撤回本人待审核变更申请")
def internship_change_withdraw(change_id: str, user=Depends(get_current_user)):
    return success(stu.internship_change_withdraw(user, change_id), message="已撤回")


@router.get("/internship/plan", summary="本人实习计划书（已发布）")
def internship_my_plan(user=Depends(get_current_user)):
    from app.modules.internship.services import internship_plan_service as plan
    return success(plan.student_my_plan(user))


@router.post("/internship/plan/acknowledge", summary="确认本人实习计划书")
def internship_plan_ack(user=Depends(get_current_user)):
    from app.modules.internship.services import internship_plan_service as plan
    return success(plan.student_acknowledge(user), message="已确认实习计划")


@router.get("/internship/plan/tasks", summary="本人实习计划任务及完成度")
def internship_plan_tasks(user=Depends(get_current_user)):
    from app.modules.internship.services import internship_plan_task_service as pt
    return success(pt.student_tasks(user))


@router.post("/internship/plan/tasks/{sort_order}/submit", summary="提交任务完成")
def internship_plan_task_submit(sort_order: int, body: dict = Body(...), user=Depends(get_current_user)):
    from app.modules.internship.services import internship_plan_task_service as pt
    return success(pt.student_submit_task(user, sort_order, body or {}), message="已提交，待指导教师确认")


@router.get("/internship/insurance", summary="本人实习保险")
def internship_my_insurance(user=Depends(get_current_user)):
    from app.modules.internship.services import internship_insurance_service as ins
    return success(ins.student_my_insurance(user))


@router.post("/internship/insurance", summary="提交本人实习保险信息")
def internship_insurance_submit(body: dict = Body(...), user=Depends(get_current_user)):
    from app.modules.internship.services import internship_insurance_service as ins
    return success(ins.student_submit(user, body or {}), message="保险信息已提交，待学校核验")


@router.post("/internship/agreements/{agreement_id}/esign/sign", summary="学生电子签签署")
def internship_agreement_esign_sign(agreement_id: str, user=Depends(get_current_user)):
    from app.modules.internship.services import internship_agreement_service as agr
    return success(agr.esign_sign(user, agreement_id, "STUDENT"), message="电子签已完成")


@router.post("/me/messages/{message_id}/read", summary="标记本人消息已读")
def me_message_read(message_id: str, user=Depends(get_current_user)):
    return success(stu.message_mark_read(user, message_id))


@router.get("/orientation/my", summary="我的迎新报到")
def orientation_my(user=Depends(get_current_user)):
    return success(stu.orientation_my(user))


@router.get("/orientation/batch-status", summary="迎新批次开放状态（公开，登录页倒计时用，无个人数据）")
def orientation_batch_status_api():
    return success(stu.orientation_batch_status())


@router.post("/orientation/collect", summary="预报到信息采集（本人，确认联系方式/生源地）")
def orientation_collect(body: dict = Body(default={}), user=Depends(get_current_user)):
    return success(stu.orientation_collect_submit(user, body), message="已提交")


@router.post("/orientation/green-channel", summary="绿色通道申请（本人提交，待审核）")
def orientation_green_channel(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.orientation_green_channel_submit(user, body), message="已提交")


@router.get("/campus-service/my", summary="我的在校服务")
def campus_service_my(user=Depends(get_current_user)):
    return success(stu.campus_service_my(user))


@router.get("/academic/my", summary="我的学业过程")
def academic_my(user=Depends(get_current_user)):
    return success(stu.academic_my(user))


@router.get("/internship/my", summary="我的岗位实习")
def internship_my(user=Depends(get_current_user)):
    return success(stu.internship_my(user))


@gd.get("/my", summary="我的毕业设计")
def graduation_my(user=Depends(get_current_user)):
    return success(stu.graduation_my(user))


@gd.get("/materials/{file_id}/download", summary="下载本人毕业设计材料")
def graduation_material_download(file_id: str, user=Depends(get_current_user)):
    """学生下载入口：不走 PC 管理端 staff 门禁，仍由材料绑定关系做本人鉴权。"""
    from fastapi.responses import FileResponse
    from app.core.exceptions import not_found
    from app.modules.graduation.services import graduation_service as gd_svc
    from app.services import audit_log

    stu._require_student(user)
    resolved = gd_svc.resolve_material_download(file_id)
    if not resolved:
        raise not_found("毕业设计材料不存在或无权访问")
    path, filename = resolved
    audit_log.record("GRADUATION_MATERIAL_DOWNLOAD", f"graduation-file:{file_id}")
    return FileResponse(str(path), filename=filename)


@gd.get("/topics", summary="选题·浏览可选题目库（已入池未满员）")
def graduation_topics(batchId: str = None, user=Depends(get_current_user)):
    return success(stu.graduation_topics(user, batch_id=batchId))


@gd.get("/active-round", summary="选题·当前进行中轮次 + 我的志愿")
def graduation_active_round(user=Depends(get_current_user)):
    return success(stu.graduation_active_round(user))


@gd.post("/choices", summary="选题·本人提交/调整志愿（对齐提交=进入待处理语义）")
def graduation_submit_choices(body: dict = Body(...), user=Depends(get_current_user)):
    round_id = body.get("roundId")
    choices = body.get("choices") or []
    return success(stu.graduation_submit_choices(user, round_id, choices), message="志愿已提交")


@gd.post("/withdraw-choices", summary="选题·本人退选（撤回本轮全部待处理志愿）")
def graduation_withdraw_choices(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_withdraw_choices(user, body.get("roundId")), message="已退选")


@gd.post("/change-request", summary="选题·发起课题变更申请（已有选题换题的唯一途径）")
def graduation_request_change(body: dict = Body(...), user=Depends(get_current_user)):
    result = stu.graduation_request_change(user, body.get("newTopicId"), body.get("reason") or "")
    return success(result, message="已提交，等待审核")


@gd.get("/change-requests/my", summary="选题·我的历史变更申请")
def graduation_my_change_requests(user=Depends(get_current_user)):
    return success(stu.graduation_my_change_requests(user))


@gd.get("/proposal", summary="开题·查看本人开题报告状态")
def graduation_proposal(user=Depends(get_current_user)):
    return success(stu.graduation_proposal(user))


@gd.post("/proposal", summary="开题·本人提交/重交开题报告")
def graduation_submit_proposal(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_submit_proposal(user, body), message="开题报告已提交")


@gd.get("/final", summary="成果·查看本人论文提交状态")
def graduation_final(user=Depends(get_current_user)):
    return success(stu.graduation_final(user))


@gd.post("/final", summary="成果·本人提交/重交论文（初稿/定稿）")
def graduation_submit_final(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_submit_final(user, body), message="论文成果已提交")


@gd.get("/taskbook", summary="任务书·查看本人任务书")
def graduation_taskbook(user=Depends(get_current_user)):
    return success(stu.graduation_taskbook(user))


@gd.post("/taskbook/confirm", summary="任务书·本人确认（含变更后重新确认）")
def graduation_taskbook_confirm(user=Depends(get_current_user)):
    return success(stu.graduation_taskbook_confirm(user), message="已确认")


@gd.get("/midterm", summary="中期检查·查看本人状态")
def graduation_midterm(user=Depends(get_current_user)):
    return success(stu.graduation_midterm(user))


@gd.post("/midterm/rectify", summary="中期检查·本人提交整改")
def graduation_midterm_rectify(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_midterm_rectify(user, body.get("content") or ""), message="已提交整改")


@gd.get("/defense", summary="答辩·查看本人答辩安排")
def graduation_defense(user=Depends(get_current_user)):
    return success(stu.graduation_defense(user))


@gd.get("/grade", summary="成绩·查看本人已发布成绩")
def graduation_grade(user=Depends(get_current_user)):
    return success(stu.graduation_grade(user))


@gd.get("/archive", summary="归档·查看本人毕业设计材料清单与归档状态")
def graduation_archive(user=Depends(get_current_user)):
    return success(stu.graduation_archive(user))


@gd.post("/grade/appeal", summary="成绩·发起更正申诉（须已发布）")
def graduation_grade_appeal(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_grade_appeal(user, body.get("reason") or ""), message="申诉已提交")


@gd.get("/peer-tasks", summary="互查·本人待互查+待整改任务")
def graduation_peer_tasks(user=Depends(get_current_user)):
    return success(stu.graduation_peer_tasks(user))


@gd.post("/peer/{pid}/submit", summary="互查·提交互查意见")
def graduation_peer_submit(pid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_peer_submit(user, pid, body.get("opinion") or ""), message="已提交")


@gd.post("/peer/{pid}/rectify", summary="互查·提交整改")
def graduation_peer_rectify(pid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_peer_rectify(user, pid, body.get("note") or ""), message="已提交整改")


@router.get("/employment/my", summary="我的就业服务")
def employment_my(user=Depends(get_current_user)):
    return success(stu.employment_my(user))


# ── 教师端·工作台 ──
@router.get("/teacher/overview", summary="教师工作台总览（本校）")
def teacher_overview(user=Depends(get_current_user)):
    return success(tea.overview(user))


@router.get("/teacher/todos", summary="教师今日待办（本校）")
def teacher_todos(user=Depends(get_current_user)):
    return success(tea.todos(user))


@router.get("/teacher/orientation", summary="教师·迎新待处理")
def teacher_orientation(user=Depends(get_current_user)):
    return success(tea.orientation(user))


@router.post("/teacher/orientation/checkin", summary="迎新老师·现场报到核验（按报到码，范围校验+审计）")
def teacher_orientation_checkin(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.orientation_checkin(user, body.get("admissionNo") or body.get("code") or ""),
                   message="核验通过")


@router.get("/teacher/orientation/today-checkins", summary="迎新老师·今日已核验列表")
def teacher_orientation_today_checkins(user=Depends(get_current_user)):
    return success(tea.orientation_today_checkins(user))


@router.get("/teacher/orientation/dashboard", summary="迎新看板（移动版·迎新老师）")
def teacher_orientation_dashboard(user=Depends(get_current_user)):
    return success(tea.orientation_dashboard(user))


@router.get("/teacher/internship/visit-plans", summary="指导巡访·本月巡访计划学生列表")
def teacher_internship_visit_plans(user=Depends(get_current_user)):
    return success(tea.internship_visit_plans(user))


@router.post("/teacher/internship/visit-plans/record", summary="记录巡访（按学生实习记录ID，范围校验+审计）")
def teacher_internship_visit_record(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.internship_visit_record(user, body.get("internshipId") or ""), message="已记录巡访")


@router.get("/teacher/campus-service", summary="教师·在校服务待处理")
def teacher_campus(user=Depends(get_current_user)):
    return success(tea.campus(user))


@router.get("/teacher/academic", summary="教师·学业预警待处理")
def teacher_academic(user=Depends(get_current_user)):
    return success(tea.academic(user))


@router.get("/teacher/internship", summary="教师·实习待批")
def teacher_internship(user=Depends(get_current_user)):
    return success(tea.internship(user))


@router.get("/teacher/graduation", summary="教师·毕设待审")
def teacher_graduation(user=Depends(get_current_user)):
    return success(tea.graduation(user))


@router.get("/teacher/employment", summary="教师·就业帮扶")
def teacher_employment(user=Depends(get_current_user)):
    return success(tea.employment(user))


@router.get("/teacher/risk-students", summary="教师·风险学生（范围过滤，替代 PC 全列表）")
def teacher_risk_students(user=Depends(get_current_user)):
    return success(tea.risk_students(user))


@router.get("/teacher/student/{student_id}", summary="教师·学生360轻量详情（权限校验）")
def teacher_student_detail(student_id: str, user=Depends(get_current_user)):
    return success(tea.student_detail(user, student_id))


@router.get("/teacher/my-classes", summary="教师·我的班级（本人担任辅导员/班主任的行政班）")
def teacher_my_classes(user=Depends(get_current_user)):
    return success(tea.my_classes(user))


@router.get("/teacher/my-students", summary="教师·我的学生（本人负责班级学生名单，可按classId下钻）")
def teacher_my_students(classId: str = None, user=Depends(get_current_user)):
    return success(tea.my_students(user, classId))


@router.get("/teacher/affairs/family-contacts/students", summary="辅导员·可登记家校联系学生名单（范围校验）")
def teacher_family_contact_students(user=Depends(get_current_user)):
    return success(tea.affairs_family_contact_students(user))


@router.get("/teacher/affairs/family-contacts", summary="辅导员·家校联系记录列表（范围校验，可按回执状态筛）")
def teacher_family_contact_list(receiptStatus: str = None, user=Depends(get_current_user)):
    return success(tea.affairs_family_contact_list(user, receiptStatus))


@router.post("/teacher/affairs/family-contacts/{student_id}", summary="辅导员·登记家校联系（owner 校验+审计）")
def teacher_family_contact_create(student_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_family_contact_create(user, student_id, body), message="已登记")


@router.post("/teacher/affairs/family-contacts/{contact_id}/receipt", summary="辅导员·登记家长回执（owner 校验）")
def teacher_family_contact_receipt(contact_id: str, body: dict = Body(default={}),
                                   user=Depends(get_current_user)):
    return success(tea.affairs_family_contact_receipt(user, contact_id, (body or {}).get("note")),
                   message="回执已登记")


@router.get("/teacher/affairs/leaves/pending", summary="辅导员·请假待审批队列（数据范围+审批节点双重收敛）")
def teacher_affairs_leave_pending(user=Depends(get_current_user)):
    return success(tea.affairs_leave_pending(user))


@router.get("/teacher/affairs/leaves/followup", summary="辅导员·请假后续处理台账（已通过/续假中/待销假/逾期）")
def teacher_affairs_leave_followup(user=Depends(get_current_user)):
    return success(tea.affairs_leave_followup(user))


@router.get("/teacher/affairs/leaves/{leave_id}", summary="辅导员·请假详情（含销假/续假/审计留痕，范围校验）")
def teacher_affairs_leave_detail(leave_id: str, user=Depends(get_current_user)):
    return success(tea.affairs_leave_detail(user, leave_id))


@router.post("/teacher/affairs/leaves/{leave_id}/approve", summary="辅导员·请假审批通过（owner+节点校验）")
def teacher_affairs_leave_approve(leave_id: str, body: dict = Body(default={}),
                                  user=Depends(get_current_user)):
    return success(tea.affairs_leave_approve(user, leave_id, (body or {}).get("comment")), message="已通过")


@router.post("/teacher/affairs/leaves/{leave_id}/reject", summary="辅导员·请假驳回（原因≥5字，owner+节点校验）")
def teacher_affairs_leave_reject(leave_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_leave_reject(user, leave_id, body.get("reason") or ""), message="已驳回")


@router.post("/teacher/affairs/leaves/{leave_id}/return", summary="辅导员·请假退回重提（原因≥5字，owner+节点校验）")
def teacher_affairs_leave_return(leave_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_leave_return(user, leave_id, body.get("reason") or ""), message="已退回")


@router.post("/teacher/affairs/leaves/{leave_id}/cancel-confirm",
             summary="辅导员·销假确认(CONFIRM)/退回(RETURN)（owner 校验）")
def teacher_affairs_leave_cancel_confirm(leave_id: str, body: dict = Body(...),
                                         user=Depends(get_current_user)):
    return success(tea.affairs_leave_cancel_confirm(
        user, leave_id, str(body.get("action") or "CONFIRM").upper(),
        body.get("actualReturnAt"), body.get("reason"), body.get("note")), message="已处理")


@router.post("/teacher/affairs/leaves/{leave_id}/proxy-cancel", summary="辅导员·代登记销假（owner 校验）")
def teacher_affairs_leave_proxy_cancel(leave_id: str, body: dict = Body(...),
                                       user=Depends(get_current_user)):
    return success(tea.affairs_leave_proxy_cancel(
        user, leave_id, body.get("actualReturnAt") or "", body.get("note")), message="已登记")


@router.post("/teacher/affairs/leaves/{leave_id}/overdue-handle",
             summary="辅导员·逾期处置登记（CONTACT/TO_HOME_SCHOOL/CLOSE，说明≥5字，owner 校验）")
def teacher_affairs_leave_overdue_handle(leave_id: str, body: dict = Body(...),
                                         user=Depends(get_current_user)):
    return success(tea.affairs_leave_overdue_handle(
        user, leave_id, str(body.get("handleType") or "").upper(), body.get("note") or ""), message="已登记")


@router.post("/teacher/affairs/leaves/{leave_id}/extension-approve",
             summary="辅导员·续假审批(APPROVE/REJECT)（owner 校验）")
def teacher_affairs_leave_extension_approve(leave_id: str, body: dict = Body(default={}),
                                            user=Depends(get_current_user)):
    return success(tea.affairs_leave_extension_approve(
        user, leave_id, str(body.get("action") or "APPROVE").upper(), body.get("reason")), message="已处理")


@router.get("/teacher/affairs/classes", summary="辅导员·我的班级（本人数据范围，供任命班干部先选班级）")
def teacher_affairs_my_classes(user=Depends(get_current_user)):
    return success(tea.affairs_my_classes(user))


@router.get("/teacher/affairs/classes/{class_id}/students", summary="辅导员·班级学生名单（范围校验，供选人）")
def teacher_affairs_class_students(class_id: str, user=Depends(get_current_user)):
    return success(tea.affairs_class_students(user, class_id))


@router.get("/teacher/affairs/classes/{class_id}/cadres", summary="辅导员·班干部名单（范围校验）")
def teacher_affairs_cadre_list(class_id: str, user=Depends(get_current_user)):
    return success(tea.affairs_cadre_list(user, class_id))


@router.post("/teacher/affairs/classes/{class_id}/cadres", summary="辅导员·任命班干部（同班同职务在任重复409，owner 校验）")
def teacher_affairs_cadre_appoint(class_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_cadre_appoint(user, class_id, body), message="已任命")


@router.post("/teacher/affairs/classes/cadres/{cadre_id}/remove", summary="辅导员·免去班干部（owner 校验）")
def teacher_affairs_cadre_remove(cadre_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    return success(tea.affairs_cadre_remove(user, cadre_id, (body or {}).get("reason")), message="已免去")


@router.get("/teacher/affairs/classes/{class_id}/materials", summary="辅导员·班级材料列表（范围校验）")
def teacher_affairs_class_materials(class_id: str, materialType: str = None, user=Depends(get_current_user)):
    return success(tea.affairs_class_materials(user, class_id, materialType))


@router.post("/teacher/affairs/classes/{class_id}/materials", summary="辅导员·新增班级材料（范围校验）")
def teacher_affairs_class_material_add(class_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_class_material_add(user, class_id, body), message="已新增")


@router.post("/teacher/affairs/classes/materials/{material_id}/void", summary="辅导员·作废班级材料（owner 校验）")
def teacher_affairs_class_material_void(material_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    return success(tea.affairs_class_material_void(user, material_id, (body or {}).get("reason")), message="已作废")


@router.get("/teacher/academic/tasks", summary="教务老师·我的教学任务（按本人 teacherKey 收敛）")
def teacher_academic_my_tasks(status: str = None, user=Depends(get_current_user)):
    return success(tea.affairs_academic_my_tasks(user, status))


@router.post("/teacher/academic/tasks/{task_id}/act", summary="教务老师·确认/退回教学任务（归属校验在服务层完成）")
def teacher_academic_task_act(task_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_academic_task_act(
        user, task_id, str(body.get("action") or "").upper(), body.get("reason")), message="已处理")


@router.get("/teacher/academic/schedule/mine", summary="教务老师·我的课表（供选择原课位发起调停课）")
def teacher_academic_my_schedule(termId: str = None, week: int = None, user=Depends(get_current_user)):
    return success(tea.affairs_academic_my_schedule(user, termId, week))


@router.post("/teacher/academic/schedule-changes/conflict-check", summary="教务老师·调停课目标课位冲突预检")
def teacher_academic_schedule_conflict_check(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_academic_schedule_conflict_check(user, body))


@router.post("/teacher/academic/schedule-changes", summary="教务老师·发起调停课（调课/停课/补课）")
def teacher_academic_schedule_submit(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_academic_schedule_submit(user, body), message="已提交")


@router.get("/teacher/academic/schedule-changes", summary="教务老师·我的调停课申请列表")
def teacher_academic_schedule_changes(status: str = None, user=Depends(get_current_user)):
    return success(tea.affairs_academic_schedule_changes(user, status))


@router.get("/teacher/academic/schedule-changes/{change_id}", summary="教务老师·调停课单详情（移动端补归属校验）")
def teacher_academic_schedule_change_detail(change_id: str, user=Depends(get_current_user)):
    return success(tea.affairs_academic_schedule_change_detail(user, change_id))


@router.post("/teacher/academic/schedule-changes/{change_id}/cancel", summary="教务老师·撤销调停课申请（终审前）")
def teacher_academic_schedule_cancel(change_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    return success(tea.affairs_academic_schedule_cancel(user, change_id, (body or {}).get("reason")), message="已撤销")


@router.get("/teacher/academic/defer/pending", summary="辅导员/任课教师·缓考待我审批（按当前身份节点自动收敛）")
def teacher_academic_defer_pending(user=Depends(get_current_user)):
    return success(tea.affairs_academic_defer_pending(user))


@router.post("/teacher/academic/defer/{defer_id}/review", summary="辅导员/任课教师·缓考审批（APPROVE/RETURN/REJECT）")
def teacher_academic_defer_review(defer_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_academic_defer_review(
        user, defer_id, str(body.get("action") or "").upper(), body.get("reason")), message="已处理")


@router.get("/teacher/academic/evaluation/batches", summary="教务老师·评教窗口列表")
def teacher_academic_evaluation_batches(user=Depends(get_current_user)):
    return success(tea.affairs_academic_evaluation_open_batches(user))


@router.get("/teacher/academic/evaluation/tasks", summary="教务老师·我的评价任务（自评/同行/督导）")
def teacher_academic_evaluation_my_tasks(evaluatorType: str, batchId: str = None, user=Depends(get_current_user)):
    return success(tea.affairs_academic_evaluation_my_tasks(user, evaluatorType, batchId))


@router.post("/teacher/academic/evaluation/tasks/{task_id}/submit", summary="教务老师·提交评价")
def teacher_academic_evaluation_submit(task_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_academic_evaluation_submit(
        user, task_id, body.get("answers"), body.get("objectiveScore"), body.get("comment")), message="已提交")


@router.get("/teacher/academic/evaluation/results", summary="教务老师·我的评价结果（跨批次聚合）")
def teacher_academic_evaluation_results(user=Depends(get_current_user)):
    return success(tea.affairs_academic_evaluation_my_results(user))


@router.post("/teacher/academic/evaluation/results/{result_id}/appeal", summary="教务老师·结果申诉（移动端补归属校验）")
def teacher_academic_evaluation_appeal(result_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_academic_evaluation_submit_appeal(
        user, result_id, body.get("reason")), message="申诉已提交")


@router.post("/teacher/notify/publish", summary="教师·发布通知（按班级/学院/全校，写入学生消息中心）")
def teacher_notify_publish(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.notify_publish(user, body), message="通知已发布")


@router.get("/teacher/dashboard", summary="教师·数据看板（真实聚合，按数据范围收敛）")
def teacher_dashboard(user=Depends(get_current_user)):
    return success(tea.dashboard(user))


# ── 教师·谈心谈话（移动端包装，复用既有 affairs_talk_service）──
@router.get("/teacher/talk", summary="教师·谈话记录列表")
def teacher_talk_list(talkType: str = None, status: str = None, studentId: str = None,
                      user=Depends(get_current_user)):
    return success(tea.talk_list(user, talkType, status, studentId))


@router.get("/teacher/talk/{talk_id}", summary="教师·谈话记录详情")
def teacher_talk_detail(talk_id: str, user=Depends(get_current_user)):
    return success(tea.talk_detail(user, talk_id))


@router.post("/teacher/talk", summary="教师·新建谈话计划（批量圈定学生）")
def teacher_talk_create(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.talk_create(user, body), message="谈话计划已创建")


@router.post("/teacher/talk/{talk_id}/record", summary="教师·填写谈话记录")
def teacher_talk_record(talk_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.talk_record(user, talk_id, body), message="谈话记录已保存")


@router.post("/teacher/talk/{talk_id}/follow-up", summary="教师·谈话跟进/办结/转风险/转家校")
def teacher_talk_follow_up(talk_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.talk_follow_up(user, talk_id, body), message="处理完成")


@router.get("/teacher/talk-stats", summary="教师·谈话工作量统计")
def teacher_talk_stats(groupBy: str = "TYPE", user=Depends(get_current_user)):
    return success(tea.talk_stats(user, groupBy))


# ── 教师·心理关注（移动端包装，严格保留既有遮蔽+授权原因红线）──
@router.get("/teacher/mental", summary="教师·心理关注名单（恒遮蔽明细）")
def teacher_mental_list(level: str = None, user=Depends(get_current_user)):
    return success(tea.mental_list(user, level))


@router.get("/teacher/mental/{ref_id}", summary="教师·心理转介详情（授权角色+原因≥5字方可见明细）")
def teacher_mental_detail(ref_id: str, reason: str = None, user=Depends(get_current_user)):
    return success(tea.mental_detail(user, ref_id, reason))


@router.post("/teacher/mental", summary="教师·登记心理转介（人工登记，系统不做任何自动诊断）")
def teacher_mental_create(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.mental_create(user, body), message="转介已登记")


@router.post("/teacher/mental/{ref_id}/follow", summary="教师·心理转介回访")
def teacher_mental_follow(ref_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.mental_follow(user, ref_id, body), message="回访已记录")


@router.post("/teacher/mental/{ref_id}/escalate", summary="教师·心理危机升级（接入风险中枢）")
def teacher_mental_escalate(ref_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.mental_escalate(user, ref_id, body), message="已升级为危机风险")


@router.post("/teacher/mental/{ref_id}/close", summary="教师·关闭心理转介（结论≥5字）")
def teacher_mental_close(ref_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.mental_close(user, ref_id, body), message="已关闭")


@router.get("/teacher/mental-stats", summary="教师·心理关注统计（仅聚合）")
def teacher_mental_stats(user=Depends(get_current_user)):
    return success(tea.mental_stats(user))


# ── 教师·消息通知设置（移动端首创，真实过滤 teacher/messages 聚合，非假开关）──
@router.get("/teacher/notify-preferences", summary="我的消息通知分类开关")
def teacher_notify_preferences(user=Depends(get_current_user)):
    return success(tea.notify_preferences(user))


@router.post("/teacher/notify-preferences", summary="设置消息通知分类开关")
def teacher_notify_set_preference(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.notify_set_preference(user, body), message="已保存")


@router.get("/teacher/messages", summary="教师·消息（范围/系统）")
def teacher_messages(user=Depends(get_current_user)):
    return success(tea.messages(user))


@router.get("/teacher/approvals", summary="教师·审批列表（mobile 轻量）")
def teacher_approvals(user=Depends(get_current_user)):
    return success(tea.approvals(user))


# ── 教师端·写操作（mobile 包装：教师校验 + 范围校验 + 审计 + 冲突 409） ──

@router.post("/teacher/approvals/{task_id}/approve", summary="教师·审批通过（范围校验+审计）")
def teacher_approval_approve(task_id: str, body: dict = Body(default={}),
                             user=Depends(get_current_user)):
    return success(tea.approval_act(user, task_id, "approve", body.get("comment") or ""),
                   message="已通过")


@router.post("/teacher/approvals/{task_id}/reject", summary="教师·审批驳回（范围校验+审计）")
def teacher_approval_reject(task_id: str, body: dict = Body(default={}),
                            user=Depends(get_current_user)):
    return success(tea.approval_act(user, task_id, "reject", body.get("reason") or ""),
                   message="已驳回")


@router.post("/teacher/internship/weekly/{report_id}/review",
             summary="教师·实习周报批阅（APPROVE/RETURN，范围校验+审计）")
def teacher_weekly_review(report_id: str, body: dict = Body(...),
                          user=Depends(get_current_user)):
    return success(tea.weekly_review(user, report_id, str(body.get("action") or "").upper(),
                                     body.get("comment") or ""), message="批阅完成")


@router.post("/teacher/internship/weekly/{report_id}/remind",
             summary="教师·逾期未交周报催交（范围校验+站内信+审计）")
def teacher_weekly_remind(report_id: str, user=Depends(get_current_user)):
    from app.modules.internship.services import internship_service as svc
    return success(svc.remind_weekly_report(report_id, user=user), message="已催交")


@router.post("/teacher/internship/exception/{exception_id}/handle",
             summary="教师·打卡异常处理（REASONABLE/ABNORMAL/TO_RISK，审计）")
def teacher_exception_handle(exception_id: str, body: dict = Body(...),
                             user=Depends(get_current_user)):
    return success(tea.exception_handle(user, exception_id, str(body.get("action") or "").upper(),
                                        body.get("comment") or ""), message="处理完成")


@router.get("/teacher/internship/makeups/pending", summary="教师·补卡审批待处理队列（范围校验）")
def teacher_makeup_pending(user=Depends(get_current_user)):
    return success(tea.makeup_pending(user))


@router.post("/teacher/internship/makeups/{makeup_id}/review",
             summary="教师·补卡审批（APPROVE/REJECT，owner+范围校验，通过真实补写打卡）")
def teacher_makeup_review(makeup_id: str, body: dict = Body(...),
                          user=Depends(get_current_user)):
    return success(tea.makeup_review(user, makeup_id, str(body.get("action") or "").upper(),
                                     body.get("comment") or ""), message="处理完成")


@router.get("/teacher/internship/leaves/pending", summary="教师·实习请假审批待处理队列（范围校验）")
def teacher_leave_pending(user=Depends(get_current_user)):
    return success(tea.leave_pending(user))


@router.post("/teacher/internship/leaves/{leave_id}/review",
             summary="教师·实习请假审批（APPROVE/REJECT，owner+范围校验）")
def teacher_leave_review(leave_id: str, body: dict = Body(...),
                         user=Depends(get_current_user)):
    return success(tea.leave_review(user, leave_id, str(body.get("action") or "").upper(),
                                    body.get("comment") or ""), message="处理完成")


@router.get("/teacher/internship/my-students", summary="指导教师·本人指导实习学生名单（范围校验，供选择记指导记录）")
def teacher_internship_my_students(user=Depends(get_current_user)):
    return success(tea.internship_my_students(user))


@router.post("/teacher/internship/guidance", summary="指导教师·新增指导记录（owner 校验，可联动转风险/通知辅导员）")
def teacher_internship_guidance_create(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.internship_guidance_create(user, body), message="指导记录已保存")


@router.get("/teacher/internship/student-evals", summary="指导教师·学生实习鉴定队列（范围校验）")
def teacher_student_eval_pending(user=Depends(get_current_user)):
    return success(tea.student_eval_pending(user))


@router.get("/teacher/internship/student-evals/{eval_id}", summary="指导教师·学生实习鉴定详情（自评/意见/审核留痕，范围校验）")
def teacher_student_eval_detail(eval_id: str, user=Depends(get_current_user)):
    return success(tea.student_eval_detail(user, eval_id))


@router.post("/teacher/internship/student-evals/{eval_id}/advisor-comment",
             summary="指导教师·填写学生鉴定意见（owner 校验）")
def teacher_student_eval_advisor_comment(eval_id: str, body: dict = Body(...),
                                         user=Depends(get_current_user)):
    return success(tea.student_eval_advisor_comment(user, eval_id, body), message="已保存意见")


@router.post("/teacher/internship/student-evals/{eval_id}/review",
             summary="指导教师·审核学生实习鉴定（APPROVE/RETURN，owner 校验）")
def teacher_student_eval_review(eval_id: str, body: dict = Body(...),
                                user=Depends(get_current_user)):
    return success(tea.student_eval_review(user, eval_id, str(body.get("action") or "").upper(),
                                           body.get("comment") or ""), message="审核完成")


@router.get("/teacher/internship/enterprise-evals", summary="指导教师·企业评价列表（范围校验）")
def teacher_enterprise_eval_pending(user=Depends(get_current_user)):
    return success(tea.enterprise_eval_pending(user))


@router.post("/teacher/internship/enterprise-evals", summary="指导教师·录入企业评价（学校录入企业纸质评价，五维评分，owner 校验）")
def teacher_enterprise_eval_create(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.enterprise_eval_create(user, body), message="已录入企业评价")


@router.post("/teacher/internship/enterprise-evals/{eval_id}/review",
             summary="指导教师·审核企业评价（APPROVE/RETURN，owner 校验）")
def teacher_enterprise_eval_review(eval_id: str, body: dict = Body(...),
                                   user=Depends(get_current_user)):
    return success(tea.enterprise_eval_review(user, eval_id, str(body.get("action") or "").upper(),
                                              body.get("comment") or ""), message="审核完成")


@router.get("/teacher/internship/insurances/pending", summary="指导教师·实习保险待核验队列（范围校验）")
def teacher_insurance_pending(user=Depends(get_current_user)):
    return success(tea.insurance_pending(user))


@router.post("/teacher/internship/insurances/{insurance_id}/verify",
             summary="指导教师·实习保险核验（APPROVE/REJECT，owner 校验）")
def teacher_insurance_verify(insurance_id: str, body: dict = Body(...),
                             user=Depends(get_current_user)):
    return success(tea.insurance_verify(user, insurance_id, str(body.get("action") or "").upper(),
                                        body.get("comment") or ""), message="核验完成")


@router.get("/teacher/internship/change-requests/pending", summary="指导教师·调岗退岗初审待处理队列（范围校验）")
def teacher_internship_change_pending(user=Depends(get_current_user)):
    return success(tea.internship_change_pending(user))


@router.post("/teacher/internship/change-requests/{change_id}/review",
             summary="指导教师·调岗退岗初审（APPROVE/REJECT，owner 校验）")
def teacher_internship_change_review(change_id: str, body: dict = Body(...),
                                     user=Depends(get_current_user)):
    return success(tea.internship_change_review(user, change_id, str(body.get("action") or "").upper(),
                                                body.get("comment") or ""), message="审核完成")


@router.get("/teacher/internship/scores", summary="指导教师·实习成绩列表（范围校验）")
def teacher_internship_score_list(user=Depends(get_current_user)):
    return success(tea.internship_score_list(user))


@router.post("/teacher/internship/scores/compute", summary="指导教师·实习成绩核算（五项加权，owner 校验）")
def teacher_internship_score_compute(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.internship_score_compute(user, body), message="核算完成")


@router.post("/teacher/internship/scores/{score_id}/publish", summary="指导教师·实习成绩发布（owner 校验，缺项不可发布）")
def teacher_internship_score_publish(score_id: str, user=Depends(get_current_user)):
    return success(tea.internship_score_publish(user, score_id), message="已发布")


@router.get("/teacher/internship/agreements/pending-school", summary="指导教师·三方协议待学校确认队列（范围校验）")
def teacher_agreement_pending_school(user=Depends(get_current_user)):
    return success(tea.agreement_pending_school(user))


@router.post("/teacher/internship/agreements/{agreement_id}/school-confirm",
             summary="指导教师·三方协议学校确认生效（owner 校验）")
def teacher_agreement_school_confirm(agreement_id: str, user=Depends(get_current_user)):
    return success(tea.agreement_school_confirm(user, agreement_id), message="已确认生效")


@router.get("/teacher/internship/process-reports", summary="指导教师·过程报告(日报/月报/总结)待批阅队列（范围校验）")
def teacher_process_report_pending(user=Depends(get_current_user)):
    return success(tea.process_report_pending(user))


@router.get("/teacher/internship/process-reports/{report_id}", summary="指导教师·过程报告详情（含正文，范围校验）")
def teacher_process_report_detail(report_id: str, user=Depends(get_current_user)):
    return success(tea.process_report_detail(user, report_id))


@router.post("/teacher/internship/process-reports/{report_id}/review",
             summary="指导教师·过程报告批阅（APPROVE/RETURN，owner 校验）")
def teacher_process_report_review(report_id: str, body: dict = Body(...),
                                  user=Depends(get_current_user)):
    return success(tea.process_report_review(user, report_id, str(body.get("action") or "").upper(),
                                             body.get("comment") or ""), message="批阅完成")


@router.get("/teacher/internship/plan-tasks/pending", summary="指导教师·实习计划任务完成度待确认队列（范围校验）")
def teacher_plan_task_pending(user=Depends(get_current_user)):
    return success(tea.plan_task_pending(user))


@router.post("/teacher/internship/plan-tasks/{progress_id}/review",
             summary="指导教师·实习计划任务完成度确认（APPROVE/REJECT，owner 校验）")
def teacher_plan_task_review(progress_id: str, body: dict = Body(...),
                             user=Depends(get_current_user)):
    return success(tea.plan_task_review(user, progress_id, str(body.get("action") or "").upper(),
                                        body.get("comment") or ""), message="处理完成")


@router.get("/teacher/internship/applications/pending", summary="指导教师·实习申请待审核队列（范围校验）")
def teacher_internship_application_pending(user=Depends(get_current_user)):
    return success(tea.internship_application_pending(user))


@router.post("/teacher/internship/applications/{application_id}/review",
             summary="指导教师·实习申请审核（APPROVE/REJECT，owner 校验，通过后落岗）")
def teacher_internship_application_review(application_id: str, body: dict = Body(...),
                                          user=Depends(get_current_user)):
    return success(tea.internship_application_review(
        user, application_id, str(body.get("action") or "").upper(), body.get("comment") or ""),
        message="审核完成")


@router.get("/teacher/graduation/proposal/{proposal_id}",
            summary="教师·毕设开题详情（批阅前真实查看：背景/方案/成果+历史版本，范围校验）")
def teacher_proposal_detail(proposal_id: str, user=Depends(get_current_user)):
    return success(tea.proposal_detail(user, proposal_id))


@router.post("/teacher/graduation/proposal/{proposal_id}/review",
             summary="教师·毕设开题批阅（APPROVE/REJECT，范围校验+审计）")
def teacher_proposal_review(proposal_id: str, body: dict = Body(...),
                            user=Depends(get_current_user)):
    return success(tea.proposal_review(user, proposal_id, str(body.get("action") or "").upper(),
                                       body.get("comment") or ""), message="批阅完成")


@router.get("/teacher/graduation/final/{final_id}",
            summary="教师·毕设成果详情（批阅前真实查看：类型/版本/查重+历史版本+真实附件，范围校验）")
def teacher_final_detail(final_id: str, user=Depends(get_current_user)):
    return success(tea.final_detail(user, final_id))


@router.post("/teacher/graduation/final/{final_id}/review",
             summary="教师·毕设成果批阅（APPROVE/REJECT，查重超标不可通过，范围校验+审计）")
def teacher_final_review(final_id: str, body: dict = Body(...),
                         user=Depends(get_current_user)):
    return success(tea.final_review(user, final_id, str(body.get("action") or "").upper(),
                                    body.get("comment") or ""), message="批阅完成")


# ── 中期检查（教师移动端）──
@router.get("/teacher/graduation/midterm/queue", summary="教师·中期待检查/待复核整改队列")
def teacher_midterm_queue(user=Depends(get_current_user)):
    return success(tea.graduation_midterm_queue(user))


@router.get("/teacher/graduation/midterm/{gd_student_id}", summary="教师·中期检查详情（范围校验）")
def teacher_midterm_detail(gd_student_id: str, user=Depends(get_current_user)):
    return success(tea.graduation_midterm_detail(user, gd_student_id))


@router.post("/teacher/graduation/midterm/{gd_student_id}/check",
             summary="教师·中期检查结论 PASS/RECTIFY/FAIL（范围校验+审计）")
def teacher_midterm_check(gd_student_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.graduation_midterm_check(user, gd_student_id, body.get("conclusion") or "",
                                                body.get("comment") or "", body.get("rectifyDeadline")),
                   message="已提交中期结论")


@router.post("/teacher/graduation/midterm/{gd_student_id}/rectify-review",
             summary="教师·复核中期整改 PASS/FAIL（范围校验+审计）")
def teacher_midterm_rectify_review(gd_student_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.graduation_midterm_rectify_review(user, gd_student_id, body.get("action") or "",
                                                         body.get("comment") or ""), message="复核完成")


# ── 评阅（评阅教师移动端）──
@router.get("/teacher/graduation/reviews/my", summary="教师·本人评阅待办任务")
def teacher_reviews_my(user=Depends(get_current_user)):
    return success(tea.graduation_my_reviews(user))


@router.post("/teacher/graduation/review/{review_id}/submit",
             summary="教师·提交评阅评分(0-100)+意见（本人任务，审计）")
def teacher_review_submit(review_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.graduation_review_submit(user, review_id, body.get("score"),
                                                body.get("opinion") or ""), message="评阅已提交")


# ── 答辩安排（教师移动端只读）──
@router.get("/teacher/graduation/defense/arrangements", summary="教师·本人指导学生答辩编排（只读）")
def teacher_defense_arrangements(user=Depends(get_current_user)):
    return success(tea.graduation_defense_arrangements(user))


# ── 成绩（教师移动端：待复核队列 + 详情 + 复核）──
@router.get("/teacher/graduation/grade/queue", summary="教师·成绩待复核队列")
def teacher_grade_queue(user=Depends(get_current_user)):
    return success(tea.graduation_grade_queue(user))


@router.get("/teacher/graduation/grade/{gd_student_id}", summary="教师·成绩三段构成详情（范围校验）")
def teacher_grade_detail(gd_student_id: str, user=Depends(get_current_user)):
    return success(tea.graduation_grade_detail(user, gd_student_id))


@router.post("/teacher/graduation/grade/{gd_student_id}/review",
             summary="教师·复核成绩 APPROVE/RETURN（RETURN 原因≥5字，范围校验+审计）")
def teacher_grade_review(gd_student_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.graduation_grade_review(user, gd_student_id, body.get("action") or "",
                                               body.get("comment") or ""), message="复核完成")


@router.get("/teacher/graduation/choices/pending", summary="教师·本人指导题目下待确认的选题志愿")
def teacher_graduation_choices_pending(user=Depends(get_current_user)):
    return success(tea.graduation_choices_pending(user))


@router.post("/teacher/graduation/choices/{choice_id}/review",
             summary="教师·确认/驳回选题志愿（CONFIRM/REJECT，范围校验+审计）")
def teacher_graduation_choice_review(choice_id: str, body: dict = Body(...),
                                     user=Depends(get_current_user)):
    return success(tea.graduation_choice_review(user, choice_id, str(body.get("action") or "").upper(),
                                                body.get("reason") or ""), message="处理完成")


@router.get("/teacher/graduation/change-requests/pending", summary="教师·与本人相关的待审选题变更申请")
def teacher_graduation_change_requests_pending(user=Depends(get_current_user)):
    return success(tea.graduation_change_requests_pending(user))


@router.post("/teacher/graduation/change-requests/{request_id}/review",
             summary="教师·审核选题变更申请（APPROVE/REJECT，范围校验+审计）")
def teacher_graduation_change_request_review(request_id: str, body: dict = Body(...),
                                             user=Depends(get_current_user)):
    return success(tea.graduation_change_request_review(
        user, request_id, str(body.get("action") or "").upper(), body.get("comment") or ""),
        message="处理完成")


@router.get("/teacher/graduation/my-students", summary="过程指导·本人指导的毕设学生列表")
def teacher_graduation_my_students(user=Depends(get_current_user)):
    return success(tea.graduation_my_students(user))


@router.post("/teacher/graduation/{gd_student_id}/guidance", summary="过程指导·快速新增指导记录（仅本人指导学生）")
def teacher_graduation_guidance_create(gd_student_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.graduation_guidance_create(user, gd_student_id, body), message="已记录")


@router.get("/teacher/graduation/taskbooks", summary="指导教师·任务书列表（范围校验）")
def teacher_graduation_taskbook_list(user=Depends(get_current_user)):
    return success(tea.graduation_taskbook_list(user))


@router.post("/teacher/graduation/taskbooks/{gd_student_id}/issue",
             summary="指导教师·下达任务书（须已分配导师且尚无任务书，owner 校验）")
def teacher_graduation_taskbook_issue(gd_student_id: str, body: dict = Body(...),
                                      user=Depends(get_current_user)):
    return success(tea.graduation_taskbook_issue(user, gd_student_id, body), message="任务书已下达")


@router.post("/teacher/graduation/taskbooks/{gd_student_id}/change",
             summary="指导教师·变更任务书（原因≥5字，仅已确认可变更，owner 校验）")
def teacher_graduation_taskbook_change(gd_student_id: str, body: dict = Body(...),
                                       user=Depends(get_current_user)):
    return success(tea.graduation_taskbook_change(user, gd_student_id, body), message="已提交变更")


@router.get("/teacher/graduation/defense/pending", summary="答辩评委·本人待评分学生名单（范围校验）")
def teacher_graduation_defense_score_pending(user=Depends(get_current_user)):
    return success(tea.graduation_defense_score_pending(user))


@router.post("/teacher/graduation/defense/{gd_student_id}/score",
             summary="答辩评委·录入/更新本人评分（judgeName 服务端强制取当前登录人，范围校验）")
def teacher_graduation_defense_score_entry(gd_student_id: str, body: dict = Body(...),
                                           user=Depends(get_current_user)):
    return success(tea.graduation_defense_score_entry(user, gd_student_id, body), message="已保存")


@router.post("/teacher/academic/warning/{warning_id}/handle",
             summary="教师·学业预警处理（CLOSE/ESCALATE，范围校验+审计）")
def teacher_warning_handle(warning_id: str, body: dict = Body(...),
                           user=Depends(get_current_user)):
    return success(tea.warning_handle(user, warning_id, str(body.get("action") or "").upper(),
                                      body.get("note") or ""), message="处理完成")


@router.post("/teacher/employment/followup", summary="教师·新增就业跟进（范围校验+审计）")
def teacher_followup_create(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.followup_create(user, body), message="跟进已记录")


@router.get("/teacher/employment/my-students", summary="就业老师·我负责的学生（供转交前选人）")
def teacher_employment_my_students(user=Depends(get_current_user)):
    return success(tea.affairs_employment_my_students(user))


@router.post("/teacher/employment/students/{student_id}/transfer", summary="就业老师·转交本人负责的学生给他人")
def teacher_employment_transfer(student_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.affairs_employment_transfer_student(
        user, student_id, (body or {}).get("newTeacher") or ""), message="已转交")


# ── 就业·企业/岗位库（校级共享主数据，路由挂 employment.company/job 权限，仅就业老师/校管可操作）──
@router.get("/teacher/employment/companies", summary="就业老师·企业列表")
def teacher_employment_companies(status: str = None, user=Depends(require_permission("employment.company.view"))):
    return success(tea.affairs_employment_companies(user, status))


@router.post("/teacher/employment/companies", summary="就业老师·新增企业")
def teacher_employment_company_create(body: dict = Body(...),
                                      user=Depends(require_permission("employment.company.manage"))):
    return success(tea.affairs_employment_company_create(user, body), message="已新增")


@router.post("/teacher/employment/companies/{company_id}/disable", summary="就业老师·停用企业（级联关闭岗位）")
def teacher_employment_company_disable(company_id: str, body: dict = Body(default={}),
                                       user=Depends(require_permission("employment.company.manage"))):
    return success(tea.affairs_employment_company_disable(user, company_id, (body or {}).get("reason")), message="已停用")


@router.get("/teacher/employment/jobs", summary="就业老师·岗位列表")
def teacher_employment_jobs(companyId: str = None, status: str = None,
                            user=Depends(require_permission("employment.job.view"))):
    return success(tea.affairs_employment_jobs(user, companyId, status))


@router.post("/teacher/employment/jobs", summary="就业老师·新增岗位")
def teacher_employment_job_create(body: dict = Body(...),
                                  user=Depends(require_permission("employment.job.manage"))):
    return success(tea.affairs_employment_job_create(user, body), message="已新增")


@router.post("/teacher/employment/jobs/{job_id}/disable", summary="就业老师·停用岗位")
def teacher_employment_job_disable(job_id: str, body: dict = Body(default={}),
                                   user=Depends(require_permission("employment.job.manage"))):
    return success(tea.affairs_employment_job_disable(user, job_id, (body or {}).get("reason")), message="已停用")


# ── 13A 学工中心·学生自视图（P7 多端收口，本人只读）──
@router.get("/affairs/overview", summary="学工·我的总览（本人各域计数）")
def affairs_overview(user=Depends(get_current_user)):
    return success(aff.overview_my(user))


@router.get("/affairs/leave/my", summary="学工·我的请假")
def affairs_leave_my(user=Depends(get_current_user)):
    return success(aff.leave_my(user))


@router.get("/affairs/aid/my", summary="学工·我的困难认定")
def affairs_aid_my(user=Depends(get_current_user)):
    return success(aff.aid_my(user))


@router.get("/affairs/funding/my", summary="学工·我的奖助")
def affairs_funding_my(user=Depends(get_current_user)):
    return success(aff.funding_my(user))


@router.get("/affairs/discipline/my", summary="学工·我的处分（仅数量）")
def affairs_discipline_my(user=Depends(get_current_user)):
    return success(aff.discipline_my(user))


@router.get("/affairs/dorm/my", summary="学工·我的宿舍（含自选开关）")
def affairs_dorm_my(user=Depends(get_current_user)):
    return success(aff.dorm_my(user))


@router.get("/affairs/dorm/select-options", summary="学工·自选床位可选项（按本人性别，受学校开关控制）")
def affairs_dorm_options(user=Depends(get_current_user)):
    return success(aff.dorm_select_options(user))


@router.get("/affairs/dorm/buildings/{building_id}/rooms", summary="学工·选床级联·某楼房间（需放开自选）")
def affairs_dorm_rooms(building_id: int, floor: int = None, user=Depends(get_current_user)):
    return success(aff.dorm_rooms(user, building_id, floor))


@router.get("/affairs/dorm/rooms/{room_id}/beds", summary="学工·选床级联·某房床位（需放开自选）")
def affairs_dorm_beds(room_id: int, user=Depends(get_current_user)):
    return success(aff.dorm_beds(user, room_id))


@router.post("/affairs/dorm/beds/{bed_id}/self-select", summary="学工·学生自选床位入住本人（未放开→403）")
def affairs_dorm_self_select(bed_id: int, user=Depends(get_current_user)):
    return success(aff.dorm_self_select(user, bed_id), message="已入住")


# ── 学生端·学生活动（D 包波次1，本人报名/签到）──
@router.get("/affairs/my-activities", summary="学工·我的活动（可报名+已报名）")
def affairs_my_activities(user=Depends(get_current_user)):
    return success(activity_svc.my_activities(user))


@router.post("/affairs/activities/{activity_id}/enroll", summary="学工·活动报名/取消（本人）")
def affairs_activity_enroll(activity_id: int, body: dict = Body(default={}), user=Depends(get_current_user)):
    return success(activity_svc.enroll(activity_id, user, (body or {}).get("action", "ENROLL")))


@router.post("/affairs/activities/{activity_id}/checkin", summary="学工·活动签到（本人，进行中）")
def affairs_activity_checkin(activity_id: int, body: dict = Body(default={}), user=Depends(get_current_user)):
    return success(activity_svc.checkin(activity_id, user, (body or {}).get("method", "MANUAL")), message="签到成功")


# ── 教师端·学工待办卡（P7）──
@router.get("/teacher/affairs", summary="教师·学工待办卡（本校按类型聚合）")
def teacher_affairs(user=Depends(get_current_user)):
    return success(aff.teacher_affairs(user))


# ── 13B 教务中心·学生自视图（P7 多端收口，本人只读 + 异动申请）──
@router.get("/academic/schedule/my", summary="教务·我的课表（最新已发布，按行政班推导）")
def academic_schedule_my(user=Depends(get_current_user)):
    return success(aa.schedule_my(user))


@router.get("/academic/transcript/my", summary="教务·我的成绩单")
def academic_transcript_my(user=Depends(get_current_user)):
    return success(aa.transcript_my(user))


@router.get("/academic/status/my", summary="教务·我的学籍与异动")
def academic_status_my(user=Depends(get_current_user)):
    return success(aa.status_my(user))


@router.post("/academic/status-change", summary="教务·学生本人发起学籍异动申请（唯一学生写入口）")
def academic_status_change(body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.submit_status_change_my(user, body), message="异动已提交")


@router.get("/academic/graduation/my", summary="教务·我的毕业进度（十一项供数维度）")
def academic_graduation_my(user=Depends(get_current_user)):
    return success(aa.graduation_progress_my(user))


@router.get("/academic/exam/my", summary="教务·我的考试（占位）")
def academic_exam_my(user=Depends(get_current_user)):
    return success(aa.exam_my(user))


@router.get("/academic/exam/defer-options", summary="教务·缓考申请·本人可选课程（已排考未开考）")
def academic_exam_defer_options(user=Depends(get_current_user)):
    return success(aa.exam_defer_options_my(user))


@router.get("/academic/exam/defer/my", summary="教务·缓考申请·本人申请列表")
def academic_exam_defer_my(status: str = None, user=Depends(get_current_user)):
    return success(aa.exam_defer_my(user, status))


@router.post("/academic/exam/defer/apply", summary="教务·缓考申请·本人提交（唯一学生写入口）")
def academic_exam_defer_apply(body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.exam_defer_apply_my(user, body), message="缓考申请已提交")


@router.post("/academic/exam/defer/{defer_id}/resubmit", summary="教务·缓考申请·退回后补材料重提")
def academic_exam_defer_resubmit(defer_id: int, user=Depends(get_current_user)):
    return success(aa.exam_defer_resubmit_my(user, defer_id), message="已重提")


@router.get("/academic/teacher-schedule/my", summary="教务·教师我的课表")
def academic_teacher_schedule_my(user=Depends(get_current_user)):
    return success(aa.teacher_schedule_my(user))


@router.get("/academic/credits/my", summary="教务·我的学分修读（真实汇总，无分类占比）")
def academic_credits_my(user=Depends(get_current_user)):
    return success(aa.credits_my(user))


@router.get("/academic/warning/my", summary="教务·我的学业预警")
def academic_warning_my(user=Depends(get_current_user)):
    return success(aa.warning_my(user))


@router.get("/academic/makeup/my", summary="教务·我的补考重修（重修+免修申请）")
def academic_makeup_my(user=Depends(get_current_user)):
    return success(aa.makeup_my(user))


@router.post("/academic/makeup/retake-apply", summary="教务·本人发起重修报名")
def academic_makeup_retake_apply(body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.retake_apply_my(user, body), message="重修报名已提交")


@router.get("/academic/selection/courses", summary="教务·网上选课·可选课程（OPEN 批次+实时余量）")
def academic_selection_courses(batch_id: str = None, user=Depends(get_current_user)):
    return success(aa.selection_courses_my(user, batch_id))


@router.post("/academic/selection/enroll", summary="教务·网上选课·本人选课")
def academic_selection_enroll(body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.selection_enroll_my(user, body), message="选课成功")


@router.post("/academic/selection/drop", summary="教务·网上选课·本人退课")
def academic_selection_drop(body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.selection_drop_my(user, body), message="已退课")


@router.get("/academic/selection/my", summary="教务·网上选课·本人选课记录")
def academic_selection_my(batch_id: str = None, user=Depends(get_current_user)):
    return success(aa.selection_records_my(user, batch_id))


# ── 成绩认定/课程替代（学生自助） ──
@router.get("/academic/recognition/my", summary="教务·我的成绩认定/课程替代申请")
def academic_recognition_my(user=Depends(get_current_user)):
    return success(aa.recognition_my(user))


@router.post("/academic/recognition/submit", summary="教务·本人提交成绩认定申请")
def academic_recognition_submit(body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.recognition_submit_my(user, body), message="认定申请已提交")


@router.get("/academic/grade-recheck/my", summary="教务·我的成绩复查申请")
def academic_recheck_my(user=Depends(get_current_user)):
    return success(aa.grade_recheck_my(user))


@router.post("/academic/grade-recheck/submit", summary="教务·本人对已发布成绩发起复查")
def academic_recheck_submit(body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.grade_recheck_submit_my(user, body), message="复查申请已提交")


@router.get("/academic/textbook/my", summary="教务·我的教材领用与费用")
def academic_textbook_my(user=Depends(get_current_user)):
    return success(aa.textbook_my(user))


@router.post("/academic/textbook/{record_id}/sign", summary="教务·学生签收本人教材")
def academic_textbook_sign(record_id: str, user=Depends(get_current_user)):
    return success(aa.textbook_sign_my(user, record_id), message="签收成功")


# ── 等级考务报名（学生自助） ──
@router.get("/academic/level-exam/my", summary="教务·考级·开放考试+我的报名")
def academic_level_exam_my(user=Depends(get_current_user)):
    return success(aa.level_exam_my(user))


@router.post("/academic/level-exam/{examId}/register", summary="教务·考级·本人报名")
def academic_level_register(examId: int = Path(...), user=Depends(get_current_user)):
    return success(aa.level_register_my(user, examId), message="报名成功")


@router.post("/academic/level-exam/{examId}/cancel", summary="教务·考级·取消报名")
def academic_level_cancel(examId: int = Path(...), user=Depends(get_current_user)):
    return success(aa.level_cancel_my(user, examId), message="已取消报名")


# ── 专业分流志愿（学生自助） ──
@router.get("/academic/major-split/my", summary="教务·分流·开放批次+我的志愿")
def academic_major_split_my(user=Depends(get_current_user)):
    return success(aa.major_split_my(user))


@router.post("/academic/major-split/submit", summary="教务·分流·提交志愿")
def academic_major_split_submit(body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.major_split_submit_my(user, body), message="志愿已提交")


@router.get("/teacher/academic/grade-tasks", summary="教师·我的成绩录入任务")
def teacher_grade_tasks(status: str = None, user=Depends(get_current_user)):
    return success(aa.teacher_grade_tasks(user, status))


@router.get("/teacher/academic/grade-tasks/{task_id}/roster", summary="教师·成绩录入·教学班名单")
def teacher_grade_roster(task_id: str, user=Depends(get_current_user)):
    return success(aa.teacher_grade_roster(task_id, user))


@router.post("/teacher/academic/grade-tasks/{task_id}/enter-score", summary="教师·成绩录入·录入单生分数")
def teacher_grade_enter_score(task_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.teacher_grade_enter_score(task_id, user, body))


@router.post("/teacher/academic/grade-tasks/{task_id}/submit", summary="教师·成绩录入·提交学院审核")
def teacher_grade_submit_task(task_id: str, user=Depends(get_current_user)):
    return success(aa.teacher_grade_submit_task(task_id, user), message="已提交学院审核")


@router.get("/teacher/academic/attendance/sessions", summary="教师·课堂考勤·我的场次列表")
def teacher_attendance_sessions(user=Depends(get_current_user)):
    return success(aa.teacher_attendance_sessions(user))


@router.post("/teacher/academic/attendance/sessions", summary="教师·课堂考勤·新建场次（按行政班圈定名单）")
def teacher_attendance_create(body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.teacher_attendance_create(user, body), message="考勤场次已创建")


@router.get("/teacher/academic/attendance/sessions/{session_id}", summary="教师·课堂考勤·场次详情+名单")
def teacher_attendance_detail(session_id: str, user=Depends(get_current_user)):
    return success(aa.teacher_attendance_detail(session_id, user))


@router.post("/teacher/academic/attendance/sessions/{session_id}/mark", summary="教师·课堂考勤·标记单生状态")
def teacher_attendance_mark(session_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.teacher_attendance_mark(session_id, user, body))


@router.post("/teacher/academic/attendance/sessions/{session_id}/submit", summary="教师·课堂考勤·提交场次（不可再改）")
def teacher_attendance_submit(session_id: str, user=Depends(get_current_user)):
    return success(aa.teacher_attendance_submit(session_id, user), message="考勤已提交")


@router.get("/teacher/academic/workload/my", summary="教师·我的工作量申报")
def teacher_workload_my(user=Depends(get_current_user)):
    return success(aa.workload_my(user))


@router.post("/teacher/academic/workload/submit", summary="教师·工作量申报（教学/监考/阅卷/出卷）")
def teacher_workload_submit(body: dict = Body(...), user=Depends(get_current_user)):
    return success(aa.workload_submit_my(user, body), message="工作量申报已提交")


router.include_router(gd)
