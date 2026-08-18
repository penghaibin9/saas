"""C-W4 grade-entry reminder without inventing a second task/message system.

Manual 催录 reuses canonical ``AA_GRADE_ENTRY`` UnifiedTodo.  The relation-aware Todo
projection first synchronizes current PRIMARY/CO_TEACHER assignees, then this command
bumps only their pending Todo versions so workbench/Teacher Today consumers refresh
from server truth.  Stale former-teacher Todos are completed by the same sync.

A dedicated grade reminder message-event template is shared/INT-owned and is not yet
registered in ``message_event_outbox_service``. This C-owned command therefore does
not misuse WARNING/SCHEDULE event codes merely to simulate push delivery. Response
explicitly reports ``messagePushReady=False`` until that shared event template lands.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission

from . import academic_affairs_grade_core_service as grade_core
from . import academic_affairs_grade_todo_teacher_relation_guard as todo_guard

_REMINDABLE = {"NOT_STARTED", "INPUTTING", "RETURNED"}
_REMIND_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN", "COLLEGE_ADMIN"}


def remind_grade_entry(task_id: int, user, reason: str) -> dict:
    """Refresh canonical pending grade-entry Todos for the current formal teachers."""
    from app.models import AaGradeTask, UnifiedTodo

    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role not in _REMIND_ROLES and (user or {}).get("userType") != "PLATFORM_SUPER_ADMIN":
        raise no_permission("仅学院教务员或教务处可催录成绩")
    reason_text = str(reason or "").strip()
    if len(reason_text) < 2:
        raise AppException("VALIDATION_ERROR", "催录原因/说明不少于2字")

    with grade_core.session() as db:
        task = db.query(AaGradeTask).filter(
            AaGradeTask.id == int(task_id),
            AaGradeTask.tenant_id == grade_core._tid(),
            AaGradeTask.is_deleted.is_(False),
        ).with_for_update().first()
        if not task:
            raise AppException("NOT_FOUND", "成绩任务不存在", http_status=404)
        if role == "COLLEGE_ADMIN":
            grade_core._check_college_scope(db, task, user)
        status = str(task.status or "").upper()
        if status not in _REMINDABLE:
            raise AppException(
                "DATA_CONFLICT",
                "仅待录入/录入中/退回待重提的成绩任务可催录",
                details={"gradeTaskId": str(task.id), "status": status},
                http_status=409,
            )

        todo_guard.sync_grade_entry_todos(db, task)
        # db_service sessions use autoflush=False; materialize newly created current
        # assignee Todos before selecting/locking the canonical pending set.
        db.flush()
        todos = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == grade_core._tid(),
            UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_type == "AA_GRADE_TASK",
            UnifiedTodo.source_biz_id == int(task.id),
            UnifiedTodo.todo_type == grade_core.TODO_GRADE_ENTRY,
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
        ).with_for_update()).all()
        if not todos:
            raise AppException(
                "DATA_CONFLICT",
                "当前正式任课教师尚未绑定可投递的真实教师账号，无法催录",
                details={"gradeTaskId": str(task.id)},
                http_status=409,
            )
        assignee_ids = []
        for todo in todos:
            todo.version = int(todo.version or 0) + 1
            assignee_ids.append(int(todo.assignee_id))

        grade_core._audit(
            db,
            "AA_GRADE_TASK",
            int(task.id),
            "GRADE_ENTRY_REMIND",
            f"assignees={','.join(str(value) for value in sorted(assignee_ids))};reason={reason_text}",
        )
        db.commit()
        return {
            "gradeTaskId": str(task.id),
            "status": status,
            "remindedCount": len(assignee_ids),
            "assigneeIds": [str(value) for value in sorted(assignee_ids)],
            "remindedAt": datetime.utcnow().isoformat(),
            "delivery": "UNIFIED_TODO_REFRESH",
            "messagePushReady": False,
            "messagePushBlocker": "INT_GRADE_REMINDER_EVENT_TEMPLATE",
        }
