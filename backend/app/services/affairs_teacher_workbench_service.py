"""教师学工跨业务待办工作台的权威查询服务。

所有计数与分页都在同一可见性条件上执行：租户、模块、状态和数据范围先收敛，
再分别做 count/group by/page query。禁止用当前页长度冒充 total。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import no_permission
from app.services.db_service import _iso, _tid, session

CONTRACT_VERSION = "AFFAIRS_TEACHER_TODO_V2"
PAGE_SIZE_MAX = 100

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
    "MATERIAL_REVIEW": "材料补交审核",
}


def _normalize_page(page: int, page_size: int) -> tuple[int, int]:
    try:
        page = int(page or 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(page_size or 20)
    except (TypeError, ValueError):
        page_size = 20
    return max(1, page), min(PAGE_SIZE_MAX, max(1, page_size))


def teacher_affairs(user: dict, *, page: int = 1, page_size: int = 20) -> dict:
    from app.models import SchoolClass, StudentProfile, UnifiedTodo
    from app.services.workbench_todo_service import _visibility_cond

    if str((user or {}).get("userType") or "").upper() == "STUDENT":
        raise no_permission("该接口仅教职工可用")

    page, page_size = _normalize_page(page, page_size)
    with session() as db:
        visibility = _visibility_cond(db, user)
        if visibility is None:
            return {
                "page": page,
                "pageSize": page_size,
                "total": 0,
                "hasMore": False,
                "cards": [],
                "items": [],
                "contractVersion": CONTRACT_VERSION,
            }

        conds = (
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
            visibility,
        )
        total = int(db.scalar(
            select(func.count()).select_from(UnifiedTodo).where(*conds)
        ) or 0)
        grouped = db.execute(
            select(UnifiedTodo.todo_type, func.count(UnifiedTodo.id))
            .where(*conds)
            .group_by(UnifiedTodo.todo_type)
            .order_by(UnifiedTodo.todo_type)
        ).all()
        rows = db.scalars(
            select(UnifiedTodo)
            .where(*conds)
            .order_by(
                UnifiedTodo.due_at.is_(None).asc(),
                UnifiedTodo.due_at.asc(),
                UnifiedTodo.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

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

        now = datetime.utcnow()
        items = []
        for row in rows:
            todo_type = str(row.todo_type or "")
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
            {"todoType": str(todo_type or ""), "label": _LABELS.get(str(todo_type or ""), str(todo_type or "")), "count": int(count)}
            for todo_type, count in grouped
        ]
        return {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "hasMore": page * page_size < total,
            "cards": cards,
            "items": items,
            "contractVersion": CONTRACT_VERSION,
        }
