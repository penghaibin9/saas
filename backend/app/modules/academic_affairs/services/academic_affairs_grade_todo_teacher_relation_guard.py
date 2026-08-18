"""C-W2/C-W5 relation-aware canonical grade-entry Todo projection.

``AA_GRADE_ENTRY`` remains the single mature UnifiedTodo type. This guard changes
only its assignee projection and protects explicit multi-teacher topology from the
legacy TeachingTask->PRIMARY auto-sync.

- formal TeachingClass exists -> all ACTIVE teacher relations covering the task-
  clamped non-occurrence week are desired assignees (PRIMARY and CO_TEACHER);
- no TeachingClass projection -> GradeTask.teacher_key migration fallback;
- desired real User IDs are upserted to PENDING; stale PENDING assignees -> DONE;
- a simple one-PRIMARY/default-window class remains in legacy auto-sync mode;
- once CO_TEACHER, split windows, or another explicit topology exists, legacy ensure
  may refresh metadata but must not rewrite relation windows/status. Changing the
  compatibility TeachingTask primary through the old endpoint while explicit mode
  exists is rejected transactionally; the formal relation management API is required.

Teacher Today remains read-only. install() also activates C-owned read guards that
consume the same authority for stale Todo filtering and PC teacher schedule.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException

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


def _explicit_topology(db, teaching_class, task):
    """Return (explicit, active_primary, active_relations) for safe legacy sync."""
    from app.models import AaTeachingClassTeacher

    active = db.scalars(select(AaTeachingClassTeacher).where(
        AaTeachingClassTeacher.tenant_id == grade_core._tid(),
        AaTeachingClassTeacher.teaching_class_id == int(teaching_class.id),
        AaTeachingClassTeacher.status == "ACTIVE",
        AaTeachingClassTeacher.is_deleted.is_(False),
    ).order_by(AaTeachingClassTeacher.role_type, AaTeachingClassTeacher.id)).all()
    primaries = [row for row in active if str(row.role_type or "").upper() == "PRIMARY"]
    cos = [row for row in active if str(row.role_type or "").upper() == "CO_TEACHER"]
    if not active:
        return False, None, active
    if len(primaries) != 1:
        return True, None, active
    primary = primaries[0]
    task_start = int(task.start_week) if task.start_week is not None else None
    task_end = int(task.end_week) if task.end_week is not None else None
    primary_start = int(primary.start_week) if primary.start_week is not None else None
    primary_end = int(primary.end_week) if primary.end_week is not None else None
    explicit = bool(
        cos
        or str(primary.teacher_key or "") != str(task.teacher_key or "")
        or primary_start != task_start
        or primary_end != task_end
    )
    return explicit, primary, active


def _sync_primary_teacher(db, teaching_class, task) -> None:
    """Preserve explicit relation topology; legacy-sync only the simple default case."""
    explicit, primary, active = _explicit_topology(db, teaching_class, task)
    if not explicit:
        _ORIGINAL_SYNC_PRIMARY(db, teaching_class, task)
    else:
        primaries = [row for row in active if str(row.role_type or "").upper() == "PRIMARY"]
        if len(primaries) != 1:
            raise AppException(
                "DATA_CONFLICT",
                "教学班显式教师关系存在 PRIMARY 数量冲突，请先在教师关系管理中修复",
                details={"teachingClassId": str(teaching_class.id), "activePrimaryCount": len(primaries)},
                http_status=409,
            )
        primary = primaries[0]
        task_key = str(task.teacher_key or "").strip()
        primary_key = str(primary.teacher_key or "").strip()
        if task_key and primary_key != task_key:
            raise AppException(
                "DATA_CONFLICT",
                "教学班已启用显式多教师/分周关系，禁止通过旧教学任务分配入口覆盖 PRIMARY；请使用教师关系管理",
                details={
                    "teachingClassId": str(teaching_class.id),
                    "formalPrimaryTeacherKey": primary_key,
                    "requestedTaskTeacherKey": task_key,
                },
                http_status=409,
            )
        if not task_key:
            task.teacher_key = primary_key
            task.teacher_id = primary.teacher_id
            task.teacher_name = primary.teacher_name
        else:
            # Metadata may follow the compatibility task, but explicit week windows
            # and relation status are formal facts and must remain untouched.
            if task.teacher_id:
                primary.teacher_id = task.teacher_id
            if task.teacher_name:
                primary.teacher_name = task.teacher_name

    # db_service sessions run with autoflush=False. Todo sync must observe the new
    # relation state produced above in the same transaction.
    db.flush()
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
