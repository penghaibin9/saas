"""学生 PC 门户 · 路由聚合（/api/v1/portal/*）。

学生端专用：不挂 require_staff 门禁（与 /mobile 一致），由服务层 _require_student 收口——
非学生令牌一律 NO_PERMISSION(403001)。家长侧只读入口在后续增量单独挂载。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import success
from app.core.security import get_current_user
from app.student_portal.services import academic_service as academic
from app.student_portal.services import common_service as common
from app.student_portal.services import graduation_service as graduation
from app.student_portal.services import guardian_service as guardian
from app.student_portal.services import home_service as home
from app.student_portal.services import messages_service as messages
from app.student_portal.services import parent_link_service as parent
from app.student_portal.services import profile_service as profile

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


# ── 首页工作台聚合 ──
@router.get("/home/overview", summary="首页工作台聚合（本人·待办/消息/预警/各域/快捷入口）")
def home_overview(user=Depends(get_current_user)):
    return success(home.overview(user))


# ── 消息通知 PC 视图 ──
@router.get("/messages", summary="消息中心（本人·分页）")
def messages_inbox(user=Depends(get_current_user),
                   page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100)):
    return success(messages.inbox(user, page, pageSize))


@router.post("/messages/{message_id}/read", summary="标记消息已读（本人）")
def messages_read(message_id: str, user=Depends(get_current_user)):
    return success(messages.mark_read(user, message_id))


@router.get("/messages/preferences", summary="通知偏好（本人）")
def messages_preferences(user=Depends(get_current_user)):
    return success(messages.get_preferences(user))


@router.post("/messages/preferences", summary="设置通知偏好（本人）")
def messages_set_preference(user=Depends(get_current_user), body: dict = Body(...)):
    return success(messages.set_preference(user, body))


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
