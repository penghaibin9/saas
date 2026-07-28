"""教师微信小程序毕业设计动作权限。

聚合移动 Router 不在 PC 毕设 Router 的依赖链内，因此这里显式复用 PC 动作权限码。
身份范围由 graduation_mobile_teacher_service 使用 mentor_id/reviewer_mentor_id/评委席位
完成；同名教师不再被临时封死，也不再回退姓名授权。
"""
from __future__ import annotations

from fastapi import Depends, Request

from app.core.exceptions import no_permission
from app.core.permissions import enforce_permission
from app.core.security import get_current_user

MOBILE_GRADUATION_ENDPOINT_PERMISSIONS: dict[str, str] = {
    "teacher_graduation_batches": "graduationDesign.dashboard.view",
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

_STABLE_ID_REQUIRED = {
    "graduationDesign.dashboard.view",
    "graduationDesign.proposal.view", "graduationDesign.proposal.review",
    "graduationDesign.final.view", "graduationDesign.final.review",
    "graduationDesign.midterm.review", "graduationDesign.review.view",
    "graduationDesign.review.submit", "graduationDesign.topic.view",
    "graduationDesign.topic.review", "graduationDesign.student.view",
    "graduationDesign.guidance.create", "graduationDesign.taskbook.view",
    "graduationDesign.taskbook.issue", "graduationDesign.taskbook.update",
    "graduationDesign.defense.view", "graduationDesign.defense.score",
}

_ADMIN_ROLES = {
    "PLATFORM_SUPER_ADMIN", "SCHOOL_ADMIN", "SAAS_ADMIN", "GRADUATION_ADMIN", "GD_ADMIN",
    "GD_COLLEGE_ADMIN", "GD_MAJOR_ADMIN", "COLLEGE_ADMIN", "GD_GRADE_ADMIN",
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
    if code in _STABLE_ID_REQUIRED and role not in _ADMIN_ROLES:
        from app.modules.graduation.services.graduation_identity import current_user_mentor
        from app.services.db_service import session

        is_external_expert = bool(user.get("expertId")) and code in {
            "graduationDesign.defense.view", "graduationDesign.defense.score",
        }
        with session() as db:
            mentor = current_user_mentor(db)
        if not mentor and not is_external_expert:
            raise no_permission("当前账号未按工号绑定稳定毕设导师/评委身份，请管理员完成绑定。")
    return checked
