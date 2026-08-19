"""C-W4 grade-entry reminder on canonical Todo + shared message outbox.

Manual 催录 first synchronizes current PRIMARY/CO_TEACHER ``AA_GRADE_ENTRY``
UnifiedTodo assignees, bumps only the current pending Todo versions, and emits one
``GRADE.ENTRY_REMINDED`` outbox event to those real teacher accounts in the same
transaction. Delivery/retry/UnifiedMessage materialization remain shared Authority.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission
from app.services.message_event_outbox_service import emit_message_event

from . import academic_affairs_grade_core_service as grade_core
from . import academic_affairs_grade_deadline_service as deadline_service
from . import academic_affairs_grade_message_event_guard as message_event_guard
from . import academic_affairs_grade_todo_teacher_relation_guard as todo_guard

_REMINDABLE = {"NOT_STARTED", "INPUTTING", "RETURNED"}
_REMIND_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN", "COLLEGE_ADMIN"}

message_event_guard.install()


def remind_grade_entry(task_id: int, user, reason: str) -> dict:
    """Refresh canonical Todos and enqueue one real message event for current teachers."""
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

        assignee_ids: list[int] = []
        versions: list[int] = []
        for todo in todos:
            todo.version = int(todo.version or 0) + 1
            assignee_ids.append(int(todo.assignee_id))
            versions.append(int(todo.version))
        assignee_ids = sorted(set(assignee_ids))

        deadline = deadline_service.deadline_projection(db, int(task.id), status=status)
        deadline_text = deadline.get("deadline") or "未设置"
        content = (
            f"《{task.course_name or '课程'}》成绩仍待录入/重提。"
            f"截止时间：{deadline_text}。催录说明：{reason_text}。请进入成绩录入任务处理。"
        )
        outbox = emit_message_event(
            db,
            event_code="GRADE.ENTRY_REMINDED",
            source_module="academic-affairs",
            source_biz_type="AA_GRADE_TASK",
            source_biz_id=int(task.id),
            recipient_refs=[{"userId": value} for value in assignee_ids],
            variables={
                "gradeTaskId": str(task.id),
                "courseName": task.course_name or "",
                "deadline": deadline.get("deadline"),
                "reason": reason_text,
            },
            content=content,
            title=f"成绩录入提醒：{task.course_name or '课程'}",
            dedup_key=f"GRADE.ENTRY_REMINDED:{task.id}:v{max(versions or [1])}",
        )

        grade_core._audit(
            db,
            "AA_GRADE_TASK",
            int(task.id),
            "GRADE_ENTRY_REMIND",
            f"assignees={','.join(str(value) for value in assignee_ids)};reason={reason_text};outbox={getattr(outbox, 'id', '')}",
        )
        db.commit()
        return {
            "gradeTaskId": str(task.id),
            "status": status,
            "remindedCount": len(assignee_ids),
            "assigneeIds": [str(value) for value in assignee_ids],
            "remindedAt": datetime.utcnow().isoformat(),
            "delivery": "UNIFIED_TODO_AND_MESSAGE_OUTBOX",
            "messagePushReady": True,
            "messageEventCode": "GRADE.ENTRY_REMINDED",
            "messageOutboxId": str(getattr(outbox, "id", "") or ""),
            "deadline": deadline.get("deadline"),
            "isOverdue": deadline.get("isOverdue"),
        }