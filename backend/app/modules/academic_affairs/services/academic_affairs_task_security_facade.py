"""教学任务工作台最终安全层。

统计域为了学校级指标曾把 ACADEMIC_TEACHER 视为全校口径；教学任务管理不能复用该特例。
本层只替换工作台范围解析：教务处/校管全校，学院/班级按统一安全上下文，其余fail-closed。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.permissions import is_super_admin

from . import academic_affairs_task_workbench_facade as _base


@dataclass
class _TaskManageScope:
    all: bool = False
    college_ids: set[int] = field(default_factory=set)
    class_ids: set[int] = field(default_factory=set)
    role: str = ""

    @property
    def blocked(self) -> bool:
        return not self.all and not self.college_ids and not self.class_ids


def _scope(user, db):
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if is_super_admin(user) or role in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}:
        return _TaskManageScope(all=True, role=role)
    context = build_affairs_context(user, db)
    if context.scope_type == "TENANT_ALL":
        return _TaskManageScope(all=True, role=role)
    allowed = context.allowed_class_ids(db)
    scope = _TaskManageScope(
        all=False,
        college_ids={int(value) for value in (context.college_ids or set())},
        class_ids={int(value) for value in (allowed or set())},
        role=role,
    )
    if scope.blocked:
        raise no_data_scope("当前身份未配置教学任务管理的学院或班级范围")
    return scope


def __getattr__(name):
    return getattr(_base, name)


# workbench函数运行时从自身globals读取_scope；替换后列表、详情、提交和动作权限统一收口。
_base._scope = _scope
