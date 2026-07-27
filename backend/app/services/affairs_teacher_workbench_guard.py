"""教师学工跨业务待办工作台。

复用 workbench_todo_service 的统一可见性：本人指派 + 数据范围内池待办；
禁止学院角色直接看到其他学院 assignee=0 的池任务。保留旧 cards，同时返回逐条 items。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import no_permission
from app.services.db_service import _iso, _tid, session

_INSTALLED = False

_LABELS = {
    "LEAVE_APPROVAL": "请假待审",
    "LEAVE_CANCEL": "销假待确认",
    "LEAVE_OVERDUE": "逾期未销假",
    "LEAVE_EXTENSION": "续假待审",
    "AID_APPROVAL": "困难认定待审",
    "AID_ADJUST": "困难等级调整待审",
    "FUNDING_APPROVAL": "奖助待审",
    "DISCIPLINE_APPROVAL": "处分待审",
    "DISCIPLINE_REMOVE": "处分解除待审",
    "RISK_HANDLE": "风险待处置",
    "DORM_TRANSFER": "调宿待审",
    "DORM_EXCEPTION": "宿舍异常待处置",
    "AID_OBJECTION_REVIEW": "困难认定异议复核",
    "FUNDING_APPEAL_REVIEW": "资助公示申诉复核",
    "DISCIPLINE_APPEAL_REVIEW": "处分申诉复核",
    "SECOND_CLASS_APPEAL_REVIEW": "第二课堂积分申诉",
}


def _workbench(user: dict) -> dict:
    from app.models import SchoolClass, StudentProfile, UnifiedTodo
    from app.services.workbench_todo_service import _visibility_cond

    if str((user or {}).get("userType") or "").upper() == "STUDENT":
        raise no_permission("该接口仅教职工可用")

    with session() as db:
        visibility = _visibility_cond(db, user)
        if visibility is None:
            return {"total": 0, "cards": [], "items": [], "contractVersion": "AFFAIRS_TEACHER_TODO_V1"}
        rows = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
            visibility,
        ).order_by(
            UnifiedTodo.due_at.is_(None).asc(),
            UnifiedTodo.due_at.asc(),
            UnifiedTodo.id.desc(),
        ).limit(100)).all()

        student_ids = {int(row.student_id) for row in rows if row.student_id}
        students = {
            int(row.id): row
            for row in db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id.in_(student_ids or {-1}),
                StudentProfile.is_deleted.is_(False),
            )).all()
        }
        class_ids = {int(row.class_id) for row in students.values() if row.class_id}
        classes = {
            int(row.id): row.class_name
            for row in db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(),
                SchoolClass.id.in_(class_ids or {-1}),
                SchoolClass.is_deleted.is_(False),
            )).all()
        }

        by_type: dict[str, int] = {}
        now = datetime.utcnow()
        items = []
        for row in rows:
            todo_type = str(row.todo_type or "")
            by_type[todo_type] = by_type.get(todo_type, 0) + 1
            student = students.get(int(row.student_id)) if row.student_id else None
            items.append({
                "todoId": str(row.id),
                "todoType": todo_type,
                "label": _LABELS.get(todo_type, todo_type or "学工待办"),
                "title": row.title or _LABELS.get(todo_type, todo_type or "学工待办"),
                "studentId": str(row.student_id or ""),
                "studentName": student.real_name if student else "",
                "studentNo": student.student_no if student else "",
                "className": classes.get(int(student.class_id), "") if student and student.class_id else "",
                "bizType": row.source_biz_type or "",
                "recordId": str(row.source_biz_id or ""),
                "dueAt": _iso(row.due_at),
                "overdue": bool(row.due_at and row.due_at < now),
                "status": row.status,
                "allowedActions": ["OPEN"],
                "actionKey": todo_type,
                "actionParams": {
                    "todoType": todo_type,
                    "recordId": str(row.source_biz_id or ""),
                    "todoId": str(row.id),
                },
            })

        cards = [
            {"todoType": key, "label": _LABELS.get(key, key), "count": count}
            for key, count in sorted(by_type.items())
        ]
        return {
            "total": len(items),
            "cards": cards,
            "items": items,
            "contractVersion": "AFFAIRS_TEACHER_TODO_V1",
        }


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import mobile_affairs_service

    mobile_affairs_service.teacher_affairs = _workbench
    _INSTALLED = True
