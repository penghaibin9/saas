"""学生困难认定/奖助申请的并发串行化门。

原子申请服务已经把申请、确认、工作流、待办、审计放在同一事务，但原先的
“查询是否重复 → 新增申请”之间没有稳定锁。两个同一学生的并发请求可能同时
看不到记录并各自插入。

本模块在原子申请事务最前面锁定当前学生主档行。同一学生的第二个请求必须等待
第一个事务提交，然后重复检查即可看到刚写入的申请并返回 DATA_CONFLICT。
不同学生互不阻塞。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid

_INSTALLED = False


def _locked_self_student(db, user):
    from app.models import StudentProfile
    from app.services.mobile_student_service import _require_student, resolve_student

    current = _require_student(user)
    resolved = resolve_student(db, current)
    if not resolved:
        raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
    locked = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.id == int(resolved.id),
        StudentProfile.is_deleted.is_(False),
    ).with_for_update()).first()
    if not locked:
        raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
    return locked


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_student_atomic_service as atomic

    atomic._self_student = _locked_self_student
    _INSTALLED = True
