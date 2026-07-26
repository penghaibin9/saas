"""教务统计/范围兼容入口。

修复公共学院参数校验中的空范围放行：受限角色未配置任何学院或班级时，即使主动传入
collegeId 也必须拒绝，不能把“空集合”解释为不限范围。
"""
from __future__ import annotations

from app.core.affairs_security import no_data_scope

from . import academic_affairs_stats_service as _legacy


def __getattr__(name):
    return getattr(_legacy, name)


def _resolve_scope(user, db):
    return _legacy._resolve_scope(user, db)


def _validate_college_param(scope, college_id):
    if getattr(scope, "blocked", False):
        raise no_data_scope("当前身份未配置任何可管理学院或班级范围")
    if college_id and not scope.all:
        allowed_colleges = set(getattr(scope, "college_ids", set()) or set())
        if allowed_colleges and int(college_id) not in allowed_colleges:
            raise no_data_scope("该学院不在您的数据范围内")
        # 仅班级直配身份没有学院集合时，后续必须继续按 class_ids 过滤；不得在此扩大为全院。
        if not allowed_colleges and not set(getattr(scope, "class_ids", set()) or set()):
            raise no_data_scope("当前身份没有可验证的学院数据范围")
