"""辅导员交接安全门：禁止迁移实习、毕设、教务等非学工任务。"""
from __future__ import annotations

from sqlalchemy import select

from app.services.db_service import _tid

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_counselor_service as counselor

    def migrate_class_work(db, class_id, from_user_id, to_user_id, reason: str) -> dict:
        from app.models import AffairsRiskRecord, CsLeave, UnifiedTodo, WorkflowInstance, WorkflowTask

        from_uid, to_uid = int(from_user_id), int(to_user_id)
        if from_uid == to_uid:
            return {"todos": 0, "workflowTasks": 0, "risks": 0}
        student_ids = counselor._class_student_ids(db, class_id)
        if not student_ids:
            return {"todos": 0, "workflowTasks": 0, "risks": 0}

        moved_todos = 0
        todos = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.assignee_id == from_uid,
            UnifiedTodo.student_id.in_(student_ids),
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
        )).all()
        for todo in todos:
            clash = db.scalars(select(UnifiedTodo).where(
                UnifiedTodo.tenant_id == _tid(),
                UnifiedTodo.source_module == todo.source_module,
                UnifiedTodo.source_biz_type == todo.source_biz_type,
                UnifiedTodo.source_biz_id == todo.source_biz_id,
                UnifiedTodo.todo_type == todo.todo_type,
                UnifiedTodo.assignee_id == to_uid,
                UnifiedTodo.is_deleted.is_(False),
            )).first()
            if clash:
                clash.status = "PENDING"
                clash.title = todo.title
                clash.version = int(clash.version or 0) + 1
                todo.status = "CANCELLED"
                todo.remark = ((todo.remark or "") + f"|交接取消→{to_uid}")[:500]
                todo.version = int(todo.version or 0) + 1
            else:
                todo.assignee_id = to_uid
                todo.remark = ((todo.remark or "") + f"|交接自{from_uid}:{reason}")[:500]
                todo.version = int(todo.version or 0) + 1
            moved_todos += 1

        leave_ids = set(db.scalars(select(CsLeave.id).where(
            CsLeave.tenant_id == _tid(), CsLeave.student_id.in_(student_ids),
            CsLeave.is_deleted.is_(False),
        )).all())
        moved_tasks = 0
        if leave_ids:
            tasks = db.scalars(select(WorkflowTask).where(
                WorkflowTask.tenant_id == _tid(), WorkflowTask.assignee_id == from_uid,
                WorkflowTask.status == "PENDING", WorkflowTask.is_deleted.is_(False),
            )).all()
            for task in tasks:
                instance = db.get(WorkflowInstance, int(task.instance_id)) if task.instance_id else None
                if not instance or (instance.source_module or "").replace("_", "-") != "student-affairs":
                    continue
                if (instance.source_biz_type or "").upper() != "LEAVE":
                    continue
                if int(instance.source_biz_id or 0) not in leave_ids:
                    continue
                task.assignee_id = to_uid
                task.version = int(task.version or 0) + 1
                moved_tasks += 1

        moved_risks = 0
        risks = db.scalars(select(AffairsRiskRecord).where(
            AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.owner_id == from_uid,
            AffairsRiskRecord.student_id.in_(student_ids), AffairsRiskRecord.status != "CLOSED",
            AffairsRiskRecord.is_deleted.is_(False),
        )).all()
        for risk in risks:
            risk.owner_id = to_uid
            risk.version = int(risk.version or 0) + 1
            moved_risks += 1

        return {"todos": moved_todos, "workflowTasks": moved_tasks, "risks": moved_risks}

    counselor._migrate_class_work = migrate_class_work
    _INSTALLED = True
