"""C-W5 live teacher authority for the mature dynamic-grade workspace.

Dynamic grade remains owned by ``academic_affairs_dynamic_grade_service``.  This
module replaces only its task-scope primitive so scheme configuration, component
roster, component score entry and score reads authorize against the *current*
formal TeachingTask teacher rather than the historical AaGradeTask.teacher_key
snapshot.

The replacement receives the caller's existing DB session.  Writes therefore lock
GradeTask and TeachingTask in the same transaction as the mature dynamic-grade
mutation; no preflight/write TOCTOU window or second grade implementation is added.
"""
from __future__ import annotations

from app.core.exceptions import not_found
from app.services.db_service import _tid

from . import academic_affairs_grade_execution_service as _execution


def _task(db, task_id, user, *, lock=False):
    from app.models import AaGradeTask

    query = db.query(AaGradeTask).filter(
        AaGradeTask.id == int(task_id),
        AaGradeTask.tenant_id == _tid(),
        AaGradeTask.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    task = query.first()
    if not task:
        raise not_found("成绩录入任务不存在")

    # For linked formal teaching tasks the live TeachingTask owner is authoritative.
    # For admin supplements (no teaching_task_id), the execution helper deliberately
    # falls back to the mature canonical course/data-scope guard.
    _execution._require_live_teacher(db, task, user, lock_owner=lock)
    return task


_task._dynamic_grade_live_teacher_authority = True


def install(dynamic_service) -> None:
    """Idempotently replace only the mature service's task-scope primitive."""
    current = getattr(dynamic_service, "_task", None)
    if not getattr(current, "_dynamic_grade_live_teacher_authority", False):
        dynamic_service._task = _task
