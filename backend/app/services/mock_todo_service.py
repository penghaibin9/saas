"""mock 待办服务。字段对齐 docs/api/04 §4.1（t_unified_todo）。"""
from __future__ import annotations

from app.core.response import paginate

_TODOS = [
    {"todoId": "todo_1001", "todoTitle": "审批·李晓萌 请假申请（3天）", "todoType": "APPROVAL",
     "sourceModule": "campus_service", "sourceBizType": "leave", "sourceBizId": "lv_2001",
     "studentId": "stu_1001", "studentName": "李晓萌", "priority": "HIGH", "status": "PENDING",
     "dueTime": "2026-07-06T18:00:00+08:00", "actionUrl": "/approvals/lv_2001", "overdue": False},
    {"todoId": "todo_1002", "todoTitle": "批阅·实习周报（第12周）", "todoType": "REVIEW",
     "sourceModule": "internship", "sourceBizType": "intern_report", "sourceBizId": "rp_3007",
     "studentId": "stu_1042", "studentName": "陈昊", "priority": "MEDIUM", "status": "PENDING",
     "dueTime": "2026-07-07T12:00:00+08:00", "actionUrl": "/intern/reports/rp_3007", "overdue": False},
    {"todoId": "todo_1003", "todoTitle": "风险跟进·连续2周未打卡", "todoType": "RISK",
     "sourceModule": "internship", "sourceBizType": "risk_alert", "sourceBizId": "rk_5005",
     "studentId": "stu_1099", "studentName": "王锐", "priority": "HIGH", "status": "PENDING",
     "dueTime": "2026-07-05T09:00:00+08:00", "actionUrl": "/students/stu_1099/risk", "overdue": True},
]


def list_todos(status: str | None = None, todo_type: str | None = None,
               page: int = 1, page_size: int = 20) -> dict:
    from app.db.session import db_enabled
    if db_enabled():
        from app.services import db_service
        items, total, by_type = db_service.list_todos(status, todo_type, page, page_size)
        data = paginate(items, total, page, page_size)
        data["countByType"] = by_type
        return data
    rows = _TODOS
    if status:
        rows = [r for r in rows if r["status"] == status]
    if todo_type:
        rows = [r for r in rows if r["todoType"] == todo_type]
    total = len(rows)
    start = (page - 1) * page_size
    data = paginate(rows[start:start + page_size], total, page, page_size)
    by_type: dict[str, int] = {}
    for r in _TODOS:
        by_type[r["todoType"]] = by_type.get(r["todoType"], 0) + 1
    data["countByType"] = by_type
    return data


def get_summary(user_ctx: dict) -> dict:
    """待办汇总（角色化：辅导员/指导教师/就业老师/管理员看到不同计数口径）。"""
    from app.db.session import db_enabled
    if db_enabled():
        from app.services import db_service
        role = (user_ctx or {}).get("currentRoleCode", "DB")
        return {"role": role, **db_service.todo_summary()}
    role = (user_ctx or {}).get("currentRoleCode", "")
    base = {"pending": 6, "overdue": 1, "nearDeadline": 2, "doneToday": 3}
    by_role = {
        "COUNSELOR": {"pending": 12, "overdue": 2, "nearDeadline": 3, "doneToday": 5},
        "GD_MENTOR": {"pending": 8, "overdue": 1, "nearDeadline": 2, "doneToday": 4},
        "EMPLOYMENT_TEACHER": {"pending": 15, "overdue": 3, "nearDeadline": 4, "doneToday": 6},
        "SCHOOL_ADMIN": {"pending": 30, "overdue": 4, "nearDeadline": 6, "doneToday": 12},
        "COLLEGE_ADMIN": {"pending": 18, "overdue": 2, "nearDeadline": 4, "doneToday": 8},
    }
    return {"role": role or "DEFAULT", **by_role.get(role, base)}


def mark_done(todo_id: str) -> dict:
    """完成待办：DB 模式走 t_unified_todo 状态流转 PENDING→DONE。"""
    from app.db.session import db_enabled
    if db_enabled():
        from app.services import db_service
        return db_service.todo_done(todo_id)
    return {"todoId": todo_id, "status": "DONE"}
