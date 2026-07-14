"""移动端聚合 API（/api/v1/mobile/*）。
学生端：只返回本人跨域数据（userType 必须 STUDENT，否则 403）。
教师端：本校待办/待处理（严格租户过滤），只读。
除 /orientation/batch-status（登录页迎新入口倒计时，登录前必须可查，不含个人数据）外，
所有接口鉴权；查不到本人档案返回空态（hasData=false），不 500。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.modules.internship.services import internship_makeup_service as mk
from app.modules.academic_affairs.services import mobile_academic_affairs_service as aa
from app.services import affairs_activity_service as activity_svc
from app.services import mobile_affairs_service as aff
from app.services import mobile_student_service as stu
from app.services import mobile_teacher_service as tea

router = APIRouter(prefix="/mobile", tags=["移动端聚合"])


# ── 学生端·我的 ──
@router.get("/me/overview", summary="学生首页总览（本人）")
def me_overview(user=Depends(get_current_user)):
    return success(stu.me_overview(user))


@router.get("/me/todos", summary="我的待办（本人）")
def me_todos(user=Depends(get_current_user)):
    return success(stu.my_todos(user))


@router.get("/me/messages", summary="我的消息（本人）")
def me_messages(user=Depends(get_current_user)):
    return success(stu.my_messages(user))


@router.get("/me/profile", summary="我的档案（本人·脱敏）")
def me_profile(user=Depends(get_current_user)):
    return success(stu.my_profile(user))


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


@router.get("/graduation/my", summary="我的毕业设计")
def graduation_my(user=Depends(get_current_user)):
    return success(stu.graduation_my(user))


@router.get("/graduation/topics", summary="选题·浏览可选题目库（已入池未满员）")
def graduation_topics(batchId: str = None, user=Depends(get_current_user)):
    return success(stu.graduation_topics(user, batch_id=batchId))


@router.get("/graduation/active-round", summary="选题·当前进行中轮次 + 我的志愿")
def graduation_active_round(user=Depends(get_current_user)):
    return success(stu.graduation_active_round(user))


@router.post("/graduation/choices", summary="选题·本人提交/调整志愿（对齐提交=进入待处理语义）")
def graduation_submit_choices(body: dict = Body(...), user=Depends(get_current_user)):
    round_id = body.get("roundId")
    choices = body.get("choices") or []
    return success(stu.graduation_submit_choices(user, round_id, choices), message="志愿已提交")


@router.post("/graduation/withdraw-choices", summary="选题·本人退选（撤回本轮全部待处理志愿）")
def graduation_withdraw_choices(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_withdraw_choices(user, body.get("roundId")), message="已退选")


@router.post("/graduation/change-request", summary="选题·发起课题变更申请（已有选题换题的唯一途径）")
def graduation_request_change(body: dict = Body(...), user=Depends(get_current_user)):
    result = stu.graduation_request_change(user, body.get("newTopicId"), body.get("reason") or "")
    return success(result, message="已提交，等待审核")


@router.get("/graduation/change-requests/my", summary="选题·我的历史变更申请")
def graduation_my_change_requests(user=Depends(get_current_user)):
    return success(stu.graduation_my_change_requests(user))


@router.get("/graduation/proposal", summary="开题·查看本人开题报告状态")
def graduation_proposal(user=Depends(get_current_user)):
    return success(stu.graduation_proposal(user))


@router.post("/graduation/proposal", summary="开题·本人提交/重交开题报告")
def graduation_submit_proposal(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_submit_proposal(user, body), message="开题报告已提交")


@router.get("/graduation/final", summary="成果·查看本人论文提交状态")
def graduation_final(user=Depends(get_current_user)):
    return success(stu.graduation_final(user))


@router.post("/graduation/final", summary="成果·本人提交/重交论文（初稿/定稿）")
def graduation_submit_final(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_submit_final(user, body), message="论文成果已提交")


@router.get("/graduation/taskbook", summary="任务书·查看本人任务书")
def graduation_taskbook(user=Depends(get_current_user)):
    return success(stu.graduation_taskbook(user))


@router.post("/graduation/taskbook/confirm", summary="任务书·本人确认（含变更后重新确认）")
def graduation_taskbook_confirm(user=Depends(get_current_user)):
    return success(stu.graduation_taskbook_confirm(user), message="已确认")


@router.get("/graduation/midterm", summary="中期检查·查看本人状态")
def graduation_midterm(user=Depends(get_current_user)):
    return success(stu.graduation_midterm(user))


@router.post("/graduation/midterm/rectify", summary="中期检查·本人提交整改")
def graduation_midterm_rectify(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_midterm_rectify(user, body.get("content") or ""), message="已提交整改")


@router.get("/graduation/defense", summary="答辩·查看本人答辩安排")
def graduation_defense(user=Depends(get_current_user)):
    return success(stu.graduation_defense(user))


@router.get("/graduation/grade", summary="成绩·查看本人已发布成绩")
def graduation_grade(user=Depends(get_current_user)):
    return success(stu.graduation_grade(user))


@router.post("/graduation/grade/appeal", summary="成绩·发起更正申诉（须已发布）")
def graduation_grade_appeal(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_grade_appeal(user, body.get("reason") or ""), message="申诉已提交")


@router.get("/graduation/peer-tasks", summary="互查·本人待互查+待整改任务")
def graduation_peer_tasks(user=Depends(get_current_user)):
    return success(stu.graduation_peer_tasks(user))


@router.post("/graduation/peer/{pid}/submit", summary="互查·提交互查意见")
def graduation_peer_submit(pid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.graduation_peer_submit(user, pid, body.get("opinion") or ""), message="已提交")


@router.post("/graduation/peer/{pid}/rectify", summary="互查·提交整改")
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


@router.post("/teacher/academic/warning/{warning_id}/handle",
             summary="教师·学业预警处理（CLOSE/ESCALATE，范围校验+审计）")
def teacher_warning_handle(warning_id: str, body: dict = Body(...),
                           user=Depends(get_current_user)):
    return success(tea.warning_handle(user, warning_id, str(body.get("action") or "").upper(),
                                      body.get("note") or ""), message="处理完成")


@router.post("/teacher/employment/followup", summary="教师·新增就业跟进（范围校验+审计）")
def teacher_followup_create(body: dict = Body(...), user=Depends(get_current_user)):
    return success(tea.followup_create(user, body), message="跟进已记录")


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


@router.get("/academic/graduation/my", summary="教务·我的毕业进度（七项）")
def academic_graduation_my(user=Depends(get_current_user)):
    return success(aa.graduation_progress_my(user))


@router.get("/academic/exam/my", summary="教务·我的考试（占位）")
def academic_exam_my(user=Depends(get_current_user)):
    return success(aa.exam_my(user))


@router.get("/academic/teacher-schedule/my", summary="教务·教师我的课表")
def academic_teacher_schedule_my(user=Depends(get_current_user)):
    return success(aa.teacher_schedule_my(user))
