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
    "teacher_graduation_workbench": "graduationDesign.dashboard.view",
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

# 老师同时持有多个毕设身份时，这些队列固定以对应身份打开（例如既是导师又是评委：答辩待评分走评委身份）。
MOBILE_IDENTITY_PREFERENCE: dict[str, str] = {
    "teacher_graduation_defense_score_pending": "GD_DEFENSE_EXPERT",
    "teacher_graduation_defense_score_entry": "GD_DEFENSE_EXPERT",
    "teacher_reviews_my": "GD_REVIEWER",
    "teacher_review_submit": "GD_REVIEWER",
    "teacher_midterm_queue": "GD_MENTOR",
    "teacher_graduation_my_students": "GD_MENTOR",
    "teacher_graduation_taskbook_list": "GD_MENTOR",
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
    is_teacher_context = "/mobile/teacher/graduation" in path
    is_material_review = (
        request.method.upper() == "POST"
        and "/mobile/graduation/material-center/materials/" in path
        and path.endswith("/review")
    )
    if not is_teacher_context and not is_material_review:
        return user

    # 材料审核路由不在 /mobile/teacher/graduation 下，但教师仍须按目标学生关系自动切到
    # 指导/评阅/秘书身份；具体材料码对应的动作权限由材料中心服务继续裁决。
    if is_material_review:
        from app.modules.graduation.services.graduation_auto_identity import identity_hint, overlay_for_request
        overlay_for_request(
            user, None, dynamic=True,
            path_params={**dict(request.path_params or {}), "__path__": path},
            hint=identity_hint(request),
        )
        return user

    endpoint = request.scope.get("endpoint")
    endpoint_name = getattr(endpoint, "__name__", "")
    code = MOBILE_GRADUATION_ENDPOINT_PERMISSIONS.get(endpoint_name)
    if not code:
        raise no_permission(f"教师移动端毕业设计接口未登记动作权限：{endpoint_name or 'unknown'}")

    request.state.permission_code = code
    from app.core.context import set_current_permission_code
    set_current_permission_code(code)
    # 老师不用切换角色：按业务关系为本次请求换上能做这件事的毕设身份。
    from app.modules.graduation.services.graduation_auto_identity import identity_hint, overlay_for_request
    overlay_for_request(user, code, path_params={**dict(request.path_params or {}), "__path__": path},
                        hint=identity_hint(request) or MOBILE_IDENTITY_PREFERENCE.get(endpoint_name))
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
