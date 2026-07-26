"""学生困难认定/奖助申请的并发与唯一键终态门。

原子申请服务已经把申请、确认、工作流、待办、审计放在同一事务，但原先的
“查询是否重复 → 新增申请”之间没有稳定锁。两个同一学生的并发请求可能同时
看不到记录并各自插入。

本模块在原子申请事务最前面锁定当前学生主档行。同一学生的第二个请求必须等待
第一个事务提交，然后重复检查即可看到刚写入的申请。数据库本身还冻结了
``tenant + batch + student`` 唯一键，因此终态申请也不能在同批次重新新建；若旧
服务仍尝试插入，唯一键异常会被准确转换为 DATA_CONFLICT，而不是向学生返回500。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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


def _is_expected_duplicate(exc: IntegrityError, constraint_name: str) -> bool:
    text = str(exc).lower()
    return constraint_name.lower() in text or ("duplicate entry" in text and "1062" in text)


def _wrap_unique_conflict(func, constraint_name: str, label: str):
    def wrapped(user, body):
        try:
            return func(user, body)
        except IntegrityError as exc:
            if not _is_expected_duplicate(exc, constraint_name):
                raise
            raise AppException(
                "DATA_CONFLICT",
                f"你在该批次已有{label}，不能重复新建；被退回的申请请进入原记录修改后重新提交",
            ) from exc

    wrapped.__name__ = getattr(func, "__name__", "student_application")
    wrapped.__doc__ = getattr(func, "__doc__", None)
    return wrapped


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_student_atomic_service as atomic
    from app.student_portal.services import affairs_service as portal

    atomic._self_student = _locked_self_student
    # atomic.install() 已先把门户与小程序统一指向原子实现；此处只在最外层转换冻结
    # 唯一键冲突，其他数据库完整性异常继续原样抛出，不能被伪装成重复申请。
    portal.aid_apply = _wrap_unique_conflict(
        portal.aid_apply, "uk_aid_apply_batch_student", "困难认定申请",
    )
    portal.funding_apply = _wrap_unique_conflict(
        portal.funding_apply, "uk_funding_app_batch_student", "奖助申请",
    )
    _INSTALLED = True
