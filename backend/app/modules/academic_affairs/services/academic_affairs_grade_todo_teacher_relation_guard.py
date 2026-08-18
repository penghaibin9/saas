"""C-W2/C-W5 relation-aware canonical grade-entry Todo projection.

``AA_GRADE_ENTRY`` remains the single mature UnifiedTodo type. This guard changes
only its assignee projection:

- formal TeachingClass exists -> all ACTIVE teacher relations covering the current /
  final teaching week are desired assignees (PRIMARY and CO_TEACHER);
- no TeachingClass projection -> GradeTask.teacher_key migration fallback;
- desired real User IDs are upserted to PENDING;
- stale PENDING assignees are marked DONE in the same transaction;
- teaching-task primary reassignment triggers a resync immediately after the formal
  TeachingClassTeacher relation is updated.

Teacher Today remains read-only. install() also activates C-owned read guards that
consume the same teacher-relation authority for stale Todo filtering and PC teacher
schedule projection; none of those render-time reads repair facts.
"""
from __future__ import annotations

from sqlalchemy import select

from . import academic_affairs_grade_core_service as grade_core
from . import academic_affairs_teacher_relation_authority as teacher_authority
from . import academic_affairs_teaching_class_core_service as teaching_class_core


def _desired_teacher_keys(db, task) -> list[str]:
    from app.models import AaTeachingClass

    teaching_task_id = getattr(task, "teaching_task_id", None)
    if teaching_task_id:
        teaching_class = db.scalars(select(AaTeachingClass).where(
            AaTeachingClass.tenant_id == grade_core._tid(),
            AaTeachingClass.teaching_task_id == int(teaching_task_id),
            AaTeachingClass.is_deleted.is_(False),
        )).first()
        if teaching_class is not None:
            if str(teaching_class.status or "").upper() != "ACTIVE":
                return []
            relations, _week = teacher_authority.active_relations(db, teaching_class)
            return sorted({
                str(row.teacher_key).strip()
                for row in relations
                if str(row.teacher_key or "").strip()
            })
    key = str(getattr(task, "teacher_key", None) or "").strip()
    return [key] if key else []


def sync_grade_entry_todos(db, task) -> bool:
    """Synchronize one grade task's pending todo assignees to formal teacher authority."""
    from app.models import UnifiedTodo

    task_id = int(getattr(task, "id", 0) or 0)
    if task_id <= 0:
        return False
    desired_keys = _desired_teacher_keys(db, task)
    desired_ids = {
        int(user_id)
        for user_id in (grade_core._resolve_grade_assignee_id(db, key) for key in desired_keys)
        if int(user_id or 0) > 0
    }
    title = f"待录成绩：{getattr(task, 'course_name', None) or '课程'}"
    rows = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == grade_core._tid(),
        UnifiedTodo.source_module == "academic-affairs",
        UnifiedTodo.source_biz_id == task_id,
        UnifiedTodo.todo_type == grade_core.TODO_GRADE_ENTRY,
        UnifiedTodo.is_deleted.is_(False),
    ).with_for_update()).all()
    by_assignee = {int(row.assignee_id or 0): row for row in rows if row.assignee_id}

    changed = False
    for assignee_id in desired_ids:
        row = by_assignee.get(assignee_id)
        if row is None:
            db.add(UnifiedTodo(
                tenant_id=grade_core._tid(),
                source_module="academic-affairs",
                source_biz_type="AA_GRADE_TASK",
                source_biz_id=task_id,
                todo_type=grade_core.TODO_GRADE_ENTRY,
                assignee_id=assignee_id,
                title=title,
                status="PENDING",
            ))
            changed = True
            continue
        if row.status != "PENDING" or row.title != title or row.source_biz_type != "AA_GRADE_TASK":
            row.status = "PENDING"
            row.title = title
            row.source_biz_type = "AA_GRADE_TASK"
            row.version = int(row.version or 0) + 1
            changed = True

    for assignee_id, row in by_assignee.items():
        if assignee_id not in desired_ids and row.status == "PENDING":
            row.status = "DONE"
            row.version = int(row.version or 0) + 1
            changed = True
    return changed or bool(desired_ids)


sync_grade_entry_todos._grade_todo_teacher_relation_guard = True


def _push_grade_entry_todo(db, task) -> bool:
    return sync_grade_entry_todos(db, task)


_push_grade_entry_todo._grade_todo_teacher_relation_guard = True


def _sync_primary_teacher(db, teaching_class, task) -> None:
    """Preserve mature relation sync, then repair an existing grade task Todo in-transaction."""
    _ORIGINAL_SYNC_PRIMARY(db, teaching_class, task)
    from app.models import AaGradeTask

    grade_task = db.scalars(select(AaGradeTask).where(
        AaGradeTask.tenant_id == grade_core._tid(),
        AaGradeTask.teaching_task_id == int(task.id),
        AaGradeTask.is_deleted.is_(False),
    ).order_by(AaGradeTask.id.asc())).first()
    if grade_task is not None and str(grade_task.status or "").upper() in {"NOT_STARTED", "INPUTTING", "RETURNED"}:
        sync_grade_entry_todos(db, grade_task)


_sync_primary_teacher._grade_todo_teacher_relation_guard = True
_ORIGINAL_SYNC_PRIMARY = teaching_class_core._sync_primary_teacher


def install() -> None:
    current = getattr(grade_core, "_push_grade_entry_todo", None)
    if not getattr(current, "_grade_todo_teacher_relation_guard", False):
        if not hasattr(grade_core, "_grade_todo_relation_original_push"):
            grade_core._grade_todo_relation_original_push = current
        grade_core._push_grade_entry_todo = _push_grade_entry_todo

    current_sync = getattr(teaching_class_core, "_sync_primary_teacher", None)
    if not getattr(current_sync, "_grade_todo_teacher_relation_guard", False):
        if not hasattr(teaching_class_core, "_grade_todo_relation_original_sync_primary"):
            teaching_class_core._grade_todo_relation_original_sync_primary = current_sync
        teaching_class_core._sync_primary_teacher = _sync_primary_teacher

    from . import academic_affairs_teacher_today_grade_todo_guard as today_todo_guard
    from . import academic_affairs_schedule_teacher_relation_guard as schedule_teacher_guard
    today_todo_guard.install()
    schedule_teacher_guard.install()
