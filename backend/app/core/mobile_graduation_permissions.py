"""Teacher-miniapp graduation action permissions.

The aggregate mobile router is outside the PC graduation router dependency. This
module makes `/mobile/teacher/graduation/*` use the same action permission codes
and fails closed for newly added endpoints that were not registered.
"""
from __future__ import annotations

from fastapi import Depends, Request

from app.core.exceptions import no_permission
from app.core.permissions import enforce_permission
from app.core.security import get_current_user

MOBILE_GRADUATION_ENDPOINT_PERMISSIONS: dict[str, str] = {
    "teacher_graduation": "graduationDesign.dashboard.view",
    "teacher_proposal_detail": "graduationDesign.proposal.view",
    "teacher_proposal_review": "graduationDesign.proposal.review",
    "teacher_final_detail": "graduationDesign.final.view",
    "teacher_final_review": "graduationDesign.final.review",
    "teacher_midterm_queue": "graduationDesign.midterm.review",
    "teacher_midterm_detail": "graduationDesign.midterm.review",
    "teacher_midterm_check": "graduationDesign.midterm.review",
    "teacher_midterm_rectify_review": "graduationDesign.midterm.review",
    "teacher_reviews_my": "graduationDesign.review.view",
    "teacher_review_submit": "graduationDesign.review.submit",
    "teacher_defense_arrangements": "graduationDesign.defense.view",
    "teacher_grade_queue": "graduationDesign.grade.view",
    "teacher_grade_detail": "graduationDesign.grade.view",
    "teacher_grade_review": "graduationDesign.grade.review",
    "teacher_graduation_choices_pending": "graduationDesign.topic.view",
    "teacher_graduation_choice_review": "graduationDesign.topic.review",
    "teacher_graduation_change_requests_pending": "graduationDesign.topic.view",
    "teacher_graduation_change_request_review": "graduationDesign.topic.review",
    "teacher_graduation_my_students": "graduationDesign.student.view",
    "teacher_graduation_guidance_create": "graduationDesign.guidance.create",
    "teacher_graduation_taskbook_list": "graduationDesign.taskbook.view",
    "teacher_graduation_taskbook_issue": "graduationDesign.taskbook.issue",
    "teacher_graduation_taskbook_change": "graduationDesign.taskbook.update",
    "teacher_graduation_defense_score_pending": "graduationDesign.defense.view",
    "teacher_graduation_defense_score_entry": "graduationDesign.defense.score",
}

_STABLE_MENTOR_REQUIRED = {
    "graduationDesign.proposal.view", "graduationDesign.proposal.review",
    "graduationDesign.final.view", "graduationDesign.final.review",
    "graduationDesign.midterm.review", "graduationDesign.review.view",
    "graduationDesign.review.submit", "graduationDesign.topic.view",
    "graduationDesign.topic.review", "graduationDesign.student.view",
    "graduationDesign.guidance.create", "graduationDesign.taskbook.view",
    "graduationDesign.taskbook.issue", "graduationDesign.taskbook.update",
    "graduationDesign.defense.view", "graduationDesign.defense.score",
}


def require_mobile_graduation_request_permission(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    path = request.url.path.rstrip("/")
    if "/mobile/teacher/graduation" not in path:
        return user

    endpoint = request.scope.get("endpoint")
    endpoint_name = getattr(endpoint, "__name__", "")
    code = MOBILE_GRADUATION_ENDPOINT_PERMISSIONS.get(endpoint_name)
    if not code:
        raise no_permission(f"教师移动端毕业设计接口未登记动作权限：{endpoint_name or 'unknown'}")

    request.state.permission_code = code
    from app.core.context import set_current_permission_code
    set_current_permission_code(code)
    checked = enforce_permission(user, code)

    role = (user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    admin_roles = {
        "SCHOOL_ADMIN", "SAAS_ADMIN", "GRADUATION_ADMIN", "GD_ADMIN",
        "GD_COLLEGE_ADMIN", "GD_MAJOR_ADMIN", "COLLEGE_ADMIN",
    }
    if code in _STABLE_MENTOR_REQUIRED and role not in admin_roles:
        from sqlalchemy import func, select
        from app.models import GraduationMentor
        from app.modules.graduation.services.graduation_identity import current_user_mentor
        from app.services.db_service import _tid, session

        is_external_expert = bool(user.get("expertId")) and code in {
            "graduationDesign.defense.view", "graduationDesign.defense.score",
        }
        with session() as db:
            mentor = current_user_mentor(db)
            same_name_count = 0
            if mentor and (mentor.teacher_name or "").strip():
                same_name_count = int(db.scalar(select(func.count()).select_from(GraduationMentor).where(
                    GraduationMentor.tenant_id == _tid(),
                    GraduationMentor.teacher_name == mentor.teacher_name,
                    GraduationMentor.is_deleted.is_(False),
                )) or 0)
        if not mentor and not is_external_expert:
            raise no_permission("当前账号未绑定稳定毕设导师/评委身份，已拒绝按姓名授权；请管理员按工号完成绑定。")
        # Legacy mobile services still contain name-based filters. Until those
        # queries are fully rewritten to mentor_id, duplicate names must fail
        # closed; otherwise two teachers named 张伟 can see each other's tasks.
        if mentor and same_name_count > 1:
            raise no_permission("当前学校存在同名毕设教师，移动端已停止按姓名授权；请使用 PC 端或完成稳定 ID 链路升级。")
    return checked
