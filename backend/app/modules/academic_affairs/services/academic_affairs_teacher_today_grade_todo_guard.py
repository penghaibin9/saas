"""C-W2 read-only stale grade Todo filter.

The write-side grade Todo projection is relation-aware for all new/reassigned tasks.
Existing databases may still contain historical ``AA_GRADE_ENTRY`` rows assigned to
a teacher who has since lost the formal TeachingClassTeacher relation. Teacher Today
must not surface those stale rows, but rendering must also never repair/create Todos.

This guard therefore filters the mature canonical Todo list against the same live
teacher authority in the caller's existing read transaction. Missing Todos for a new
teacher remain a projection/backfill concern, not a read-side write.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException

from . import academic_affairs_grade_execution_service as grade_execution
from . import academic_affairs_teacher_today_work_service as today_work


def pending_grade_todos(db, user) -> list[dict]:
    from app.models import AaGradeTask

    rows = _ORIGINAL_PENDING(db, user)
    if not rows:
        return []
    task_ids = sorted({
        int(row.get("gradeTaskId"))
        for row in rows
        if str(row.get("gradeTaskId") or "").isdigit()
    })
    tasks = db.scalars(select(AaGradeTask).where(
        AaGradeTask.tenant_id == today_work._tid(),
        AaGradeTask.id.in_(task_ids or [-1]),
        AaGradeTask.is_deleted.is_(False),
    )).all()
    task_by_id = {int(row.id): row for row in tasks}
    output = []
    for item in rows:
        task_id = int(item.get("gradeTaskId") or 0)
        task = task_by_id.get(task_id)
        if task is None:
            continue
        try:
            grade_execution._require_live_teacher(db, task, user, lock_owner=False)
        except AppException:
            continue
        output.append(item)
    return output


pending_grade_todos._teacher_today_live_grade_todo_guard = True
_ORIGINAL_PENDING = today_work.pending_grade_todos


def install() -> None:
    current = getattr(today_work, "pending_grade_todos", None)
    if getattr(current, "_teacher_today_live_grade_todo_guard", False):
        return
    if not hasattr(today_work, "_live_grade_todo_guard_original_pending"):
        today_work._live_grade_todo_guard_original_pending = current
    today_work.pending_grade_todos = pending_grade_todos
