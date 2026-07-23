"""学生 PC 门户 · 路由聚合（/api/v1/portal/*）。

学生端专用：不挂 require_staff 门禁（与 /mobile 一致），由服务层 _require_student 收口——
非学生令牌一律 NO_PERMISSION(403001)。家长侧只读入口在后续增量单独挂载。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import success
from app.core.security import get_current_user
from app.student_portal.services import academic_service as academic
from app.student_portal.services import affairs_service as affairs
from app.student_portal.services import common_service as common
from app.student_portal.services import employment_service as employment
from app.student_portal.services import graduation_service as graduation
from app.student_portal.services import guardian_service as guardian
from app.student_portal.services import internship_service as internship
from app.student_portal.services import home_service as home
from app.student_portal.services import messages_service as messages
from app.student_portal.services import orientation_service as orientation
from app.student_portal.services import parent_link_service as parent
from app.student_portal.services import profile_service as profile
from app.student_portal.services import service_hall_service as service_hall

router = APIRouter(prefix="/portal", tags=["学生PC门户"])


# ── 毕业设计（第2期）：任务书 PC 电子确认 + 打印 ──
@router.get("/graduation/taskbook", summary="查看本人毕设任务书（本人）")
def graduation_taskbook(user=Depends(get_current_user)):
    return success(graduation.taskbook(user))


@router.post("/graduation/taskbook/sign", summary="任务书电子确认（可靠留痕+置确认态）")
def graduation_taskbook_sign(user=Depends(get_current_user), body: dict = Body(...)):
    return success(graduation.taskbook_sign(user, body))


@router.post("/graduation/taskbook/print", summary="任务书打印留痕（本人）")
def graduation_taskbook_print(user=Depends(get_current_user), body: dict = Body(...)):
    return success(graduation.taskbook_print(user, body))


@router.get("/graduation/proposal", summary="查看本人开题报告（本人）")
def graduation_proposal(user=Depends(get_current_user)):
    return success(graduation.proposal(user))


@router.post("/graduation/proposal/submit", summary="提交/重交开题报告（长文本+附件）")
def graduation_proposal_submit(user=Depends(get_current_user), body: dict = Body(...)):
    return success(graduation.submit_proposal(user, body))


@router.get("/graduation/midterm", summary="查看本人中期检查（含导师批注）")
def graduation_midterm(user=Depends(get_current_user)):
    return success(graduation.midterm(user))


@router.post("/graduation/midterm/rectify", summary="对照批注提交整改（本人）")
def graduation_midterm_rectify(user=Depends(get_current_user), body: dict = Body(...)):
    return success(graduation.midterm_rectify(user, body))


@router.get("/graduation/final", summary="查看本人论文成果（含查重率）")
def graduation_final(user=Depends(get_current_user)):
    return success(graduation.final(user))


@router.post("/graduation/final/submit", summary="提交/重交论文成果（大附件）")
def graduation_final_submit(user=Depends(get_current_user), body: dict = Body(...)):
    return success(graduation.submit_final(user, body))


@router.get("/graduation/defense", summary="查看本人答辩安排（本人）")
def graduation_defense(user=Depends(get_current_user)):
    return success(graduation.defense(user))


@router.get("/graduation/grade", summary="查看本人毕设成绩（本人）")
def graduation_grade(user=Depends(get_current_user)):
    return success(graduation.grade(user))


@router.post("/graduation/grade/appeal", summary="毕设成绩申诉（本人）")
def graduation_grade_appeal(user=Depends(get_current_user), body: dict = Body(...)):
    return success(graduation.grade_appeal(user, body))


# ── 教务学业（第3期）：我的成绩单 + 打印 ──
@router.get("/academic/transcript", summary="我的成绩单（本人·含GPA）")
def academic_transcript(user=Depends(get_current_user)):
    return success(academic.transcript(user))


@router.post("/academic/transcript/print", summary="成绩单打印留痕（本人）")
def academic_transcript_print(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.transcript_print(user, body))


@router.get("/academic/schedule", summary="我的课表（本人·最新已发布）")
def academic_schedule(user=Depends(get_current_user)):
    return success(academic.schedule(user))


@router.post("/academic/schedule/print", summary="课表打印留痕（本人）")
def academic_schedule_print(user=Depends(get_current_user), body: dict = Body(None)):
    return success(academic.schedule_print(user, body or {}))


@router.get("/academic/course-selection", summary="可选课程（本人·OPEN批次）")
def academic_course_selection(user=Depends(get_current_user), batchId: str | None = Query(None)):
    return success(academic.selection_courses(user, batchId))


@router.post("/academic/course-selection/enroll", summary="选课（本人）")
def academic_course_enroll(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.selection_enroll(user, body))


@router.post("/academic/course-selection/drop", summary="退课（本人）")
def academic_course_drop(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.selection_drop(user, body))


@router.get("/academic/course-selection/records", summary="我的选课记录（本人）")
def academic_course_records(user=Depends(get_current_user), batchId: str | None = Query(None)):
    return success(academic.selection_records(user, batchId))


@router.get("/academic/status", summary="我的学籍状态与异动记录（本人）")
def academic_status(user=Depends(get_current_user)):
    return success(academic.status(user))


@router.get("/academic/transfer-options", summary="异动可选目标专业/同专业班级（本人）")
def academic_transfer_options(user=Depends(get_current_user)):
    return success(academic.transfer_options(user))


@router.post("/academic/status-change", summary="发起学籍异动申请（本人）")
def academic_status_change(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.submit_status_change(user, body))


@router.post("/academic/status-change/print", summary="打印学籍异动申请审批表（本人）")
def academic_status_change_print(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.status_change_print(user, body))


@router.get("/academic/exam", summary="我的考试（本人）")
def academic_exam(user=Depends(get_current_user)):
    return success(academic.exam(user))


@router.get("/academic/exam/defer", summary="我的缓考申请（本人）")
def academic_exam_defer(user=Depends(get_current_user), status: str | None = Query(None)):
    return success(academic.exam_defer(user, status))


@router.post("/academic/exam/defer/apply", summary="发起缓考申请（本人）")
def academic_exam_defer_apply(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.exam_defer_apply(user, body))


@router.post("/academic/exam/defer/{defer_id}/resubmit", summary="缓考退回后补材料重提（本人）")
def academic_exam_defer_resubmit(defer_id: str, user=Depends(get_current_user)):
    return success(academic.exam_defer_resubmit(user, defer_id), message="已重提")


@router.get("/academic/makeup", summary="我的补考重修与免修（本人）")
def academic_makeup(user=Depends(get_current_user)):
    return success(academic.makeup(user))


@router.get("/academic/makeup/options", summary="重修/免修可选挂科与未及格课程（本人）")
def academic_makeup_options(user=Depends(get_current_user)):
    return success(academic.makeup_options(user))

@router.post("/academic/retake/apply", summary="发起重修报名（本人）")
def academic_retake_apply(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.retake_apply(user, body))


@router.post("/academic/exemption/apply", summary="发起免修申请（本人）")
def academic_exemption_apply(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.exemption_apply(user, body))


@router.get("/academic/registration", summary="我的注册批次与自助状态（本人）")
def academic_registration(user=Depends(get_current_user)):
    return success(academic.registration(user))


@router.post("/academic/registration/{batch_id}/register", summary="本人完成注册")
def academic_registration_register(batch_id: str, user=Depends(get_current_user)):
    return success(academic.registration_register(user, batch_id), message="注册成功")


@router.post("/academic/registration/{batch_id}/defer", summary="本人申请暂缓注册")
def academic_registration_defer(batch_id: str, user=Depends(get_current_user), body: dict = Body(default={})):
    return success(academic.registration_defer(user, batch_id, body or {}), message="暂缓申请已提交")


@router.get("/academic/attendance", summary="我的课堂考勤（本人·只读）")
def academic_attendance(user=Depends(get_current_user)):
    return success(academic.attendance(user))


@router.get("/academic/calendar", summary="当前学期校历（本人·只读）")
def academic_calendar(user=Depends(get_current_user)):
    return success(academic.calendar(user))


@router.get("/academic/clearance", summary="我的清考结果（本人·只读）")
def academic_clearance(user=Depends(get_current_user)):
    return success(academic.clearance(user))


@router.post("/academic/exam/ticket/print", summary="准考证打印留痕（本人）")
def academic_exam_ticket_print(user=Depends(get_current_user), body: dict = Body(default={})):
    return success(academic.exam_ticket_print(user, body or {}))

@router.get("/academic/graduation-audit", summary="毕业资格自查（本人·进度/学分/预警）")
def academic_graduation_audit(user=Depends(get_current_user)):
    return success(academic.graduation_audit(user))


@router.get("/academic/evaluation/tasks", summary="学生评教·开放窗口内本班任务（匿名）")
def academic_evaluation_tasks(user=Depends(get_current_user)):
    return success(academic.evaluation_tasks(user))


@router.post("/academic/evaluation/submit", summary="学生评教·匿名提交")
def academic_evaluation_submit(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.evaluation_submit(user, body), message="已提交")


@router.get("/academic/exam/defer/options", summary="可申请缓考的考试课程（本人·未开考）")
def academic_exam_defer_options(user=Depends(get_current_user)):
    return success(academic.exam_defer_options(user))


@router.get("/academic/grade-recheck", summary="我的成绩复查申请（本人）")
def academic_grade_recheck(user=Depends(get_current_user)):
    return success(academic.grade_recheck(user))


@router.post("/academic/grade-recheck", summary="发起成绩复查（本人·已发布成绩）")
def academic_grade_recheck_submit(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.grade_recheck_submit(user, body), message="复查申请已提交")


@router.get("/academic/textbook", summary="我的教材领用与费用（本人）")
def academic_textbook(user=Depends(get_current_user)):
    return success(academic.textbook(user))


@router.post("/academic/textbook/{record_id}/sign", summary="签收教材（本人）")
def academic_textbook_sign(record_id: str, user=Depends(get_current_user)):
    return success(academic.textbook_sign(user, record_id), message="已签收")


@router.get("/academic/level-exam", summary="等级考试·可报名与我的报名（本人）")
def academic_level_exam(user=Depends(get_current_user)):
    return success(academic.level_exam(user))


@router.post("/academic/level-exam/{exam_id}/register", summary="等级考试报名（本人）")
def academic_level_register(exam_id: str, user=Depends(get_current_user)):
    return success(academic.level_register(user, exam_id), message="已报名")


@router.post("/academic/level-exam/{exam_id}/cancel", summary="取消等级考试报名（本人）")
def academic_level_cancel(exam_id: str, user=Depends(get_current_user)):
    return success(academic.level_cancel(user, exam_id), message="已取消")


@router.get("/academic/major-split", summary="专业分流·开放批次与我的志愿（本人）")
def academic_major_split(user=Depends(get_current_user)):
    return success(academic.major_split(user))


@router.post("/academic/major-split/submit", summary="提交/修改专业分流志愿（本人）")
def academic_major_split_submit(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.major_split_submit(user, body), message="志愿已提交")


@router.get("/academic/credits", summary="我的学分修读（本人）")
def academic_credits(user=Depends(get_current_user)):
    return success(academic.credits(user))


@router.get("/academic/warning", summary="我的学业预警（本人·只读）")
def academic_warning(user=Depends(get_current_user)):
    return success(academic.warning(user))


@router.get("/academic/recognition", summary="我的成绩认定/课程替代（本人）")
def academic_recognition(user=Depends(get_current_user)):
    return success(academic.recognition(user))


@router.post("/academic/recognition", summary="提交成绩认定申请（本人）")
def academic_recognition_submit(user=Depends(get_current_user), body: dict = Body(...)):
    return success(academic.recognition_submit(user, body), message="认定申请已提交")


# ── 学工事务（第4期）：自视图聚合 + 通用事务申请 + 打印 ──
@router.get("/affairs/overview", summary="学工总览（本人）")
def affairs_overview(user=Depends(get_current_user)):
    return success(affairs.overview(user))


@router.get("/affairs/leave", summary="我的请假（本人）")
def affairs_leave(user=Depends(get_current_user)):
    return success(affairs.leave(user))


@router.post("/affairs/leave/{leave_id}/resubmit", summary="退回后本人重新提交请假")
def affairs_leave_resubmit(leave_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    from app.services import affairs_leave_service as leave_svc
    reason = str((body or {}).get("reason") or "").strip() or None
    result = leave_svc.resubmit(leave_id, user, self_only=True, reason=reason)
    return success(result, message="已重新提交，等待辅导员审批")


@router.post("/affairs/leave/{leave_id}/cancel", summary="本人发起销假")
def affairs_leave_cancel(leave_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    return success(affairs.leave_cancel(user, leave_id, body or {}), message="销假已提交，等待辅导员确认")



@router.post("/affairs/leave/{leave_id}/extension", summary="本人发起续假")
def affairs_leave_extension(leave_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(affairs.leave_extend(user, leave_id, body or {}), message="续假已提交，等待辅导员审批")


@router.get("/affairs/dorm", summary="我的宿舍（本人只读）")
def affairs_dorm(user=Depends(get_current_user)):
    return success(affairs.dorm(user))

@router.get("/affairs/talk", summary="我的谈心谈话（本人摘要）")
def affairs_talk(user=Depends(get_current_user)):
    return success(affairs.talk(user))


@router.get("/affairs/funding", summary="我的奖助勤贷补（本人）")
def affairs_funding(user=Depends(get_current_user)):
    return success(affairs.funding(user))


@router.get("/affairs/aid", summary="我的困难资助等级（本人）")
def affairs_aid(user=Depends(get_current_user)):
    return success(affairs.aid(user))


@router.get("/affairs/discipline", summary="我的违纪处分（本人·数量）")
def affairs_discipline(user=Depends(get_current_user)):
    return success(affairs.discipline(user))


@router.post("/affairs/service-apply", summary="通用学工事务申请（请假/咨询/工单，本人）")
def affairs_service_apply(user=Depends(get_current_user), body: dict = Body(...)):
    return success(affairs.service_apply(user, body))


@router.post("/affairs/print", summary="打印学工回执/请假条（本人）")
def affairs_print(user=Depends(get_current_user), body: dict = Body(...)):
    return success(affairs.print_doc(user, body))


@router.get("/affairs/psy/questions", summary="心理自评·题目（本人）")
def affairs_psy_questions(user=Depends(get_current_user)):
    return success(affairs.psy_questions(user))


@router.post("/affairs/psy/submit", summary="心理自评·提交（本人）")
def affairs_psy_submit(user=Depends(get_current_user), body: dict = Body(...)):
    return success(affairs.psy_submit(user, body))


@router.get("/affairs/psy/history", summary="心理自评·历史（本人）")
def affairs_psy_history(user=Depends(get_current_user)):
    return success(affairs.psy_history(user))


@router.get("/affairs/applications", summary="我的申请（本人聚合）")
def affairs_applications(user=Depends(get_current_user)):
    return success(affairs.applications(user))


@router.post("/affairs/discipline/appeal", summary="违纪处分申辩/申诉（本人）")
def affairs_discipline_appeal(user=Depends(get_current_user), body: dict = Body(...)):
    return success(affairs.discipline_appeal(user, body))


@router.get("/affairs/funding/batches", summary="当前开放的奖助勤贷补批次（本人可申请）")
def affairs_funding_batches(user=Depends(get_current_user)):
    return success(affairs.funding_batches_open(user))


@router.post("/affairs/funding/apply", summary="奖助勤贷补申请（本人·承诺书签署）")
def affairs_funding_apply(user=Depends(get_current_user), body: dict = Body(...)):
    return success(affairs.funding_apply(user, body))


@router.post("/affairs/funding/appeal", summary="公示期本人对资助结果申诉")
def affairs_funding_appeal(user=Depends(get_current_user), body: dict = Body(...)):
    return success(affairs.funding_appeal(user, body), message="申诉已提交")


@router.get("/affairs/aid/batches", summary="当前开放的困难认定批次（本人可申请）")
def affairs_aid_batches(user=Depends(get_current_user)):
    return success(affairs.aid_batches_open(user))


@router.post("/affairs/aid/apply", summary="困难认定申请（本人·长表+承诺书签署）")
def affairs_aid_apply(user=Depends(get_current_user), body: dict = Body(...)):
    return success(affairs.aid_apply(user, body))


@router.post("/affairs/aid/objection", summary="公示期本人对困难认定结果提异议")
def affairs_aid_objection(user=Depends(get_current_user), body: dict = Body(...)):
    return success(affairs.aid_objection(user, body), message="异议已提交")


@router.get("/affairs/activities", summary="活动二课/社团（本人可报名）")
def affairs_activities(user=Depends(get_current_user),
                       page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100)):
    return success(affairs.activities(user, page, pageSize))


@router.get("/affairs/activities/my", summary="我报名的活动（本人）")
def affairs_activities_my(user=Depends(get_current_user)):
    return success(affairs.activities_my(user))


@router.post("/affairs/activities/{activity_id}/enroll", summary="活动报名（本人）")
def affairs_activity_enroll(activity_id: str, user=Depends(get_current_user)):
    return success(affairs.activity_enroll(user, activity_id))


# ── 岗位实习（第5期）：我的实习 + 打卡/请假/自评/补卡 + 周报/协议/申诉 ──
@router.get("/internship/my", summary="我的实习（本人）")
def internship_my(user=Depends(get_current_user)):
    return success(internship.my(user))


@router.get("/internship/leaves", summary="本人实习请假列表")
def internship_leaves(user=Depends(get_current_user)):
    return success(internship.leave_list(user))


@router.post("/internship/leaves/apply", summary="实习请假申请（本人）")
def internship_leave_apply(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.leave_apply(user, body))


@router.post("/internship/leaves/{leave_id}/return", summary="实习销假（本人）")
def internship_leave_return(leave_id: str, user=Depends(get_current_user), body: dict = Body(default={})):
    return success(internship.leave_return(user, leave_id, body or {}))


@router.post("/internship/leaves/{leave_id}/withdraw", summary="撤回本人实习请假")
def internship_leave_withdraw(leave_id: str, user=Depends(get_current_user)):
    return success(internship.leave_withdraw(user, leave_id), message="已撤回")


@router.post("/internship/checkin", summary="实习打卡（本人）")
def internship_checkin(user=Depends(get_current_user), body: dict = Body(default={})):
    return success(internship.checkin(user, body or {}))


@router.post("/internship/self-eval", summary="实习自评提交（本人）")
def internship_self_eval(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.self_eval_submit(user, body))


@router.get("/internship/makeup", summary="本人补卡申请列表")
def internship_makeup_list(user=Depends(get_current_user)):
    return success(internship.makeup_list(user))


@router.post("/internship/makeup", summary="补卡申请（本人）")
def internship_makeup_apply(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.makeup_apply(user, body))


@router.post("/internship/makeup/{makeup_id}/withdraw", summary="撤回本人补卡申请")
def internship_makeup_withdraw(makeup_id: str, user=Depends(get_current_user)):
    return success(internship.makeup_withdraw(user, makeup_id), message="已撤回")


@router.get("/internship/intention", summary="本人岗位意向")
def internship_intention_my(user=Depends(get_current_user)):
    return success(internship.intention_my(user))


@router.post("/internship/intention", summary="提交/更新岗位意向（本人）")
def internship_intention_save(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.intention_save(user, body))


@router.post("/internship/intention/submit", summary="正式提交岗位意向（本人）")
def internship_intention_submit(user=Depends(get_current_user)):
    return success(internship.intention_submit(user), message="意向已提交")


@router.post("/internship/intention/withdraw", summary="撤回岗位意向（本人）")
def internship_intention_withdraw(user=Depends(get_current_user)):
    return success(internship.intention_withdraw(user), message="意向已撤回")


@router.get("/internship/applications", summary="本人岗位/自主实习申请列表")
def internship_applications(user=Depends(get_current_user)):
    return success(internship.applications_my(user))


@router.post("/internship/applications", summary="提交岗位/自主实习申请（本人）")
def internship_application_submit(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.application_submit(user, body))


@router.get("/internship/change", summary="本人调岗/退岗申请列表")
def internship_change_list(user=Depends(get_current_user)):
    return success(internship.change_list(user))


@router.post("/internship/change", summary="调岗/退岗申请（本人）")
def internship_change_apply(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.change_apply(user, body))


@router.get("/internship/agreements", summary="本人实习协议列表")
def internship_agreements(user=Depends(get_current_user)):
    return success(internship.agreements_my(user))


@router.get("/internship/agreements/{agreement_id}", summary="本人实习协议详情")
def internship_agreement_detail(agreement_id: str, user=Depends(get_current_user)):
    return success(internship.agreement_detail(user, agreement_id))


@router.post("/internship/agreements/{agreement_id}/confirm", summary="确认/驳回实习协议（本人）")
def internship_agreement_confirm(agreement_id: str, user=Depends(get_current_user), body: dict = Body(default={})):
    return success(internship.agreement_confirm(user, agreement_id, body or {}))


@router.get("/internship/insurance", summary="本人实习保险")
def internship_insurance_my(user=Depends(get_current_user)):
    return success(internship.insurance_my(user))


@router.post("/internship/insurance", summary="提交实习保险信息（本人）")
def internship_insurance_save(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.insurance_save(user, body or {}), message="保险信息已提交")


@router.get("/internship/plan", summary="本人实习计划")
def internship_plan_my(user=Depends(get_current_user)):
    return success(internship.plan_my(user))


@router.post("/internship/plan/acknowledge", summary="确认实习计划（本人）")
def internship_plan_ack(user=Depends(get_current_user)):
    return success(internship.plan_ack(user), message="已确认实习计划")


@router.get("/internship/enterprises", summary="可浏览企业岗位（本人）")
def internship_enterprises(city: str = "", user=Depends(get_current_user)):
    return success(internship.enterprises(user, city or ""))

@router.post("/internship/help", summary="实习求助/风险上报（本人，轻量）")
def internship_help(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.help_report(user, body or {}), message="求助已提交")



@router.post("/internship/weekly/submit", summary="提交实习周报（本人）")
def internship_weekly_submit(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.weekly_submit(user, body))


@router.post("/internship/report/submit", summary="提交实习月报/总结长文档（本人）")
def internship_report_submit(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.report_submit(user, body))


@router.post("/internship/agreement/print", summary="打印实习三方协议（本人）")
def internship_agreement_print(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.agreement_print(user, body))


@router.post("/internship/score/appeal", summary="实习成绩申诉（本人）")
def internship_score_appeal(user=Depends(get_current_user), body: dict = Body(...)):
    return success(internship.score_appeal(user, body))


# ── 就业服务（第5期）：我的就业 + 去向登记 + 打印 ──
@router.get("/employment/my", summary="我的就业（本人）")
def employment_my(user=Depends(get_current_user)):
    return success(employment.my(user))


@router.post("/employment/destination", summary="就业去向登记（本人）")
def employment_destination(user=Depends(get_current_user), body: dict = Body(...)):
    return success(employment.destination_register(user, body))


@router.post("/employment/destination/print", summary="打印就业协议/回执（本人）")
def employment_destination_print(user=Depends(get_current_user), body: dict = Body(...)):
    return success(employment.destination_print(user, body))


# ── 迎新报到（第5期）──
@router.get("/orientation/my", summary="我的迎新报到（本人）")
def orientation_my(user=Depends(get_current_user)):
    return success(orientation.my(user))


@router.post("/orientation/collect", summary="预报到信息采集（本人）")
def orientation_collect(user=Depends(get_current_user), body: dict = Body(...)):
    return success(orientation.collect(user, body))


@router.post("/orientation/green-channel", summary="绿色通道申请（本人）")
def orientation_green_channel(user=Depends(get_current_user), body: dict = Body(...)):
    return success(orientation.green_channel(user, body))


@router.post("/orientation/print", summary="打印迎新报到回执（本人）")
def orientation_print(user=Depends(get_current_user), body: dict = Body(...)):
    return success(orientation.print_receipt(user, body))


# ── 办事大厅（第5期收口）──
@router.get("/service-hall/catalog", summary="办事大厅目录（本人·已开通模块）")
def service_hall_catalog(user=Depends(get_current_user)):
    return success(service_hall.catalog(user))


# ── 首页工作台聚合 ──
@router.get("/home/overview", summary="首页工作台聚合（本人·待办/消息/预警/各域/快捷入口）")
def home_overview(user=Depends(get_current_user)):
    return success(home.overview(user))


# ── 消息通知 PC 视图 ──
@router.get("/messages", summary="消息中心（本人·分页）")
def messages_inbox(user=Depends(get_current_user),
                   page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100)):
    return success(messages.inbox(user, page, pageSize))


@router.post("/messages/read-all", summary="全部标为已读（本人）")
def messages_read_all(user=Depends(get_current_user)):
    return success(messages.mark_read_all(user), message="已全部标为已读")


@router.get("/messages/preferences", summary="通知偏好（本人）")
def messages_preferences(user=Depends(get_current_user)):
    return success(messages.get_preferences(user))


@router.post("/messages/preferences", summary="设置通知偏好（本人）")
def messages_set_preference(user=Depends(get_current_user), body: dict = Body(...)):
    return success(messages.set_preference(user, body))


@router.post("/messages/{message_id}/read", summary="标记消息已读（本人）")
def messages_read(message_id: str, user=Depends(get_current_user)):
    return success(messages.mark_read(user, message_id))


@router.post("/messages/{message_id}/receipt", summary="消息确认回执（本人）")
def messages_receipt(message_id: str, user=Depends(get_current_user)):
    return success(messages.ack_receipt(user, message_id), message="已确认")


# ── PC 重活公共底座：电子签署（可插拔）+ 打印/导出留痕 ──
@router.post("/common/sign", summary="电子签署（默认可靠留痕；法律级待采购接入）")
def common_sign(user=Depends(get_current_user), body: dict = Body(...)):
    return success(common.sign(user, body))


@router.post("/common/print-log", summary="打印留痕（本人·审计+水印）")
def common_print_log(user=Depends(get_current_user), body: dict = Body(...)):
    return success(common.print_log(user, body))


@router.post("/common/export-log", summary="导出留痕（本人·审计+水印）")
def common_export_log(user=Depends(get_current_user), body: dict = Body(...)):
    return success(common.export_log(user, body))


# ── 我的档案（学籍信息只读 + 敏感明文授权查看）──
@router.get("/profile/enrollment", summary="我的学籍信息（本人·只读·默认脱敏）")
def profile_enrollment(user=Depends(get_current_user)):
    return success(profile.enrollment(user))


@router.post("/profile/sensitive", summary="授权查看敏感字段明文（本人·填原因·留痕）")
def profile_sensitive(user=Depends(get_current_user), body: dict = Body(...)):
    return success(profile.sensitive_view(user, body))


# ── 家长授权代理（学生本人侧管理）──
@router.get("/parent/guardians", summary="我授权的家长列表（本人·手机号脱敏）")
def list_guardians(user=Depends(get_current_user)):
    return success(parent.list_guardians(user))


@router.post("/parent/guardians", summary="授权一个家长代理只读查看（本人）")
def bind_guardian(user=Depends(get_current_user), body: dict = Body(...)):
    return success(parent.bind_guardian(user, body))


@router.post("/parent/guardians/{link_id}/revoke", summary="撤销某个家长的查看授权（本人）")
def revoke_guardian(link_id: str, user=Depends(get_current_user)):
    return success(parent.revoke_guardian(user, link_id))


# ── 家长（proxy）侧：验证码登录 + 只读查看（otp/login 免登录）──
@router.post("/guardian/otp", summary="家长登录·请求验证码（公开）")
def guardian_otp(body: dict = Body(...)):
    return success(guardian.request_otp(body))


@router.post("/guardian/login", summary="家长登录·手机号+验证码（公开，签发GUARDIAN令牌）")
def guardian_login(body: dict = Body(...)):
    return success(guardian.login(body))


@router.get("/guardian/students", summary="家长查看被授权学生（只读·授权范围）")
def guardian_students(user=Depends(get_current_user)):
    return success(guardian.list_students(user))


@router.get("/guardian/students/{link_id}/overview", summary="家长查看被授权学生四范围只读概览（本人授权范围内）")
def guardian_student_overview(link_id: str, user=Depends(get_current_user)):
    return success(guardian.student_overview(user, link_id))
