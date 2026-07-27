"""P0-05 等级考试学生本人身份守卫。"""
from __future__ import annotations

from app.core.context import get_current_user_ctx
from app.core.exceptions import not_found

from . import academic_affairs_level_exam_service as _base


def __getattr__(name):
    return getattr(_base, name)


def _student_profile(db):
    from app.services.mobile_student_identity_facade import resolve_student

    profile = resolve_student(db, get_current_user_ctx() or {})
    if not profile:
        raise not_found("当前账号尚未绑定唯一学生档案")
    return profile


_base._student_profile = _student_profile
