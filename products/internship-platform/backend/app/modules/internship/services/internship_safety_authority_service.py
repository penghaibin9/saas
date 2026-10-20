"""安全教育学校端职责分层。

保留现有 permissionCode 兼容学校自定义角色，同时在业务层收紧角色职责：
- 课程配置：学校/学院/实习管理员；
- 分配课程、审核结果：上述管理员或校内指导教师；
- 学生办理：只走 student-only 服务，不经过本模块。
"""
from __future__ import annotations

from app.core.exceptions import no_permission
from app.core.permissions import is_super_admin
from app.modules.internship.services import internship_safety_service as safety

_ADMIN_ROLES = {
    "SCHOOL_ADMIN", "COLLEGE_ADMIN", "INTERNSHIP_ADMIN",
    "INTERN_ADMIN", "COLLEGE_INTERNSHIP_ADMIN",
}
_REVIEW_ROLES = {*_ADMIN_ROLES, "INTERN_MENTOR"}


def _role(user) -> str:
    return str(
        (user or {}).get("currentRoleCode") or
        (user or {}).get("roleCode") or
        (user or {}).get("userType") or ""
    ).strip().upper()


def _require(user, roles, message):
    if is_super_admin(user or {}):
        return
    if _role(user) not in roles:
        raise no_permission(message)


def create_course(body, user):
    _require(user, _ADMIN_ROLES, "安全教育课程配置仅限学校、学院或实习管理员")
    return safety.create_course(body, user=user)


def ensure_completion(body, user):
    _require(user, _REVIEW_ROLES, "安全教育任务分配仅限授权管理员或校内指导教师")
    return safety.ensure_completion(body, user=user)


def review_completion(completion_id, body, user):
    _require(user, _REVIEW_ROLES, "安全教育审核仅限授权管理员或校内指导教师")
    payload = body or {}
    return safety.teacher_review_completion(
        completion_id,
        score=payload.get("score"),
        action=payload.get("action"),
        comment=payload.get("comment"),
        expected_version=payload.get("expectedVersion"),
        user=user,
    )
