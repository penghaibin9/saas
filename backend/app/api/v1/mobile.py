"""移动端聚合 API（/api/v1/mobile/*）。
学生端：只返回本人跨域数据（userType 必须 STUDENT，否则 403）。
教师端：本校待办/待处理（严格租户过滤），只读。
所有接口鉴权；查不到本人档案返回空态（hasData=false），不 500。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
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


@router.post("/campus-service/apply", summary="提交在校服务申请（本人）")
def campus_service_apply(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.campus_service_apply(user, body))


@router.post("/internship/weekly", summary="提交实习周报（本人）")
def internship_weekly(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.internship_weekly_submit(user, body))


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
