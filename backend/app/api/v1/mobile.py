"""移动端聚合 API（/api/v1/mobile/*）。
学生端：只返回本人跨域数据（userType 必须 STUDENT，否则 403）。
教师端：本校待办/待处理（严格租户过滤），只读。
所有接口鉴权；查不到本人档案返回空态（hasData=false），不 500。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.services import internship_makeup_service as mk
from app.services import mobile_academic_affairs_service as aa
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
    from app.services import internship_leave_service as lv
    return success(lv.my_leaves(user))


@router.post("/internship/leave", summary="实习请假申请（本人，待指导教师审批）")
def internship_leave_apply(body: dict = Body(...), user=Depends(get_current_user)):
    from app.services import internship_leave_service as lv
    return success(lv.apply(user, body or {}), message="请假申请已提交")


@router.post("/internship/leave/{leave_id}/withdraw", summary="撤回本人请假申请")
def internship_leave_withdraw(leave_id: str, user=Depends(get_current_user)):
    from app.services import internship_leave_service as lv
    return success(lv.withdraw(user, leave_id), message="已撤回")


@router.get("/internship/agreements", summary="本人三方协议列表")
def internship_my_agreements(user=Depends(get_current_user)):
    from app.services import internship_agreement_service as agr
    return success(agr.my_agreements(user))


@router.post("/internship/agreements/{agreement_id}/confirm", summary="本人确认/驳回三方协议")
def internship_agreement_confirm(agreement_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    from app.services import internship_agreement_service as agr
    b = body or {}
    return success(agr.student_confirm(user, agreement_id, (b.get("action") or "").upper(),
                                       b.get("reason") or ""), message="已提交")


@router.get("/internship/self-eval", summary="本人实习自评/鉴定")
def internship_my_self_eval(user=Depends(get_current_user)):
    from app.services import internship_student_eval_service as se
    return success(se.my_eval(user))


@router.post("/internship/self-eval", summary="提交/重交本人实习自评（总结/收获/问题）")
def internship_submit_self_eval(body: dict = Body(...), user=Depends(get_current_user)):
    from app.services import internship_student_eval_service as se
    return success(se.student_submit(user, body or {}), message="自评已提交")


@router.post("/me/messages/{message_id}/read", summary="标记本人消息已读")
def me_message_read(message_id: str, user=Depends(get_current_user)):
    return success(stu.message_mark_read(user, message_id))


@router.get("/orientation/my", summary="我的迎新报到")
def orientation_my(user=Depends(get_current_user)):
    return success(stu.orientation_my(user))


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


@router.post("/teacher/internship/exception/{exception_id}/handle",
             summary="教师·打卡异常处理（REASONABLE/ABNORMAL/TO_RISK，审计）")
def teacher_exception_handle(exception_id: str, body: dict = Body(...),
                             user=Depends(get_current_user)):
    return success(tea.exception_handle(user, exception_id, str(body.get("action") or "").upper(),
                                        body.get("comment") or ""), message="处理完成")


@router.post("/teacher/graduation/proposal/{proposal_id}/review",
             summary="教师·毕设开题批阅（APPROVE/REJECT，范围校验+审计）")
def teacher_proposal_review(proposal_id: str, body: dict = Body(...),
                            user=Depends(get_current_user)):
    return success(tea.proposal_review(user, proposal_id, str(body.get("action") or "").upper(),
                                       body.get("comment") or ""), message="批阅完成")


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
