"""C-W5 adapter: bind grade execution to formal TeachingClassTeacher authority.

The grade execution service already centralizes fixed-score, import, submit and
correction teacher checks. This adapter replaces only that scope primitive; mature
grade state machines remain untouched. Dynamic-grade scope delegates to the same
execution primitive, so installing this module closes both fixed and dynamic paths.
"""
from __future__ import annotations

from types import SimpleNamespace

from . import academic_affairs_grade_core_service as core
from . import academic_affairs_grade_execution_service as execution
from . import academic_affairs_teacher_relation_authority as teacher_authority


def _require_live_teacher(db, task, user, *, lock_owner: bool = False):
    if execution._is_scope_admin(user):
        return None
    teaching_task_id = getattr(task, "teaching_task_id", None)
    if not teaching_task_id:
        core._check_course_scope(task, user)
        return {"source": "GRADE_TASK_COMPAT_SCOPE"}
    return teacher_authority.require_teacher(
        db,
        SimpleNamespace(id=int(teaching_task_id)),
        user,
        lock=lock_owner,
    )


_require_live_teacher._formal_teacher_relation_authority = True


def install() -> None:
    current = getattr(execution, "_require_live_teacher", None)
    if getattr(current, "_formal_teacher_relation_authority", False):
        return
    if not hasattr(execution, "_task_teacher_snapshot_guard_original_require"):
        execution._task_teacher_snapshot_guard_original_require = current
    execution._require_live_teacher = _require_live_teacher
