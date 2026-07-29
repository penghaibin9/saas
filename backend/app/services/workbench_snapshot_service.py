"""教师工作台只读快照：一次鉴权后聚合摘要、分类、最近待办和消息角标。

不改变权限口径，复用 workbench_todo_service 的 SQL 可见性条件；不缓存敏感明细，
仅减少前端重复请求、重复范围解析和数据库会话创建。
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import case, func, select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session
from app.services import workbench_todo_service as todo_svc


def snapshot(user: dict, page_size: int = 8) -> dict:
    from app.models import UnifiedTodo
    from app.services import message_center_service as message_svc

    size = max(1, min(20, int(page_size or 8)))
    now = todo_svc._utc_now()
    soon = now + timedelta(hours=24)
    today_start = todo_svc._local_today_start_utc()

    with session() as db:
        visibility = todo_svc._visibility_cond(db, user)
        if visibility is None:
            summary = {"pending": 0, "overdue": 0, "nearDeadline": 0, "doneToday": 0}
            by_type = {}
            items = []
        else:
            base = [
                UnifiedTodo.tenant_id == _tid(),
                UnifiedTodo.is_deleted.is_(False),
                visibility,
            ]
            pending = UnifiedTodo.status == "PENDING"
            row = db.execute(select(
                func.sum(case((pending, 1), else_=0)),
                func.sum(case((pending & UnifiedTodo.due_at.is_not(None)
                               & (UnifiedTodo.due_at < now), 1), else_=0)),
                func.sum(case((pending & UnifiedTodo.due_at.is_not(None)
                               & (UnifiedTodo.due_at >= now)
                               & (UnifiedTodo.due_at <= soon), 1), else_=0)),
                func.sum(case(((UnifiedTodo.status == "DONE")
                               & UnifiedTodo.updated_at.is_not(None)
                               & (UnifiedTodo.updated_at >= today_start), 1), else_=0)),
            ).where(*base)).one()
            summary = {
                "pending": int(row[0] or 0),
                "overdue": int(row[1] or 0),
                "nearDeadline": int(row[2] or 0),
                "doneToday": int(row[3] or 0),
            }
            type_rows = db.execute(select(UnifiedTodo.todo_type, func.count())
                                   .where(*base, pending)
                                   .group_by(UnifiedTodo.todo_type)).all()
            by_type = {todo_type: int(count) for todo_type, count in type_rows}
            rows = db.scalars(select(UnifiedTodo).where(*base, pending)
                              .order_by(UnifiedTodo.due_at.is_(None).asc(),
                                        UnifiedTodo.due_at.asc(), UnifiedTodo.id.desc())
                              .limit(size)).all()
            items = [todo_svc._todo_dict(item) for item in rows]

    try:
        messages = message_svc.count_messages(user)
    except AppException as exc:
        if exc.code != "NO_PERMISSION":
            raise
        # 消息权限是独立能力。没有消息查看权限时只隐藏角标，不能拖垮待办工作台。
        messages = {"unread": 0, "pendingAck": 0}

    role = str((user or {}).get("currentRoleCode") or (user or {}).get("roleCode") or "")
    return {
        "summary": {**summary, "role": role},
        "count": {"total": summary["pending"], "byType": by_type},
        "todos": {
            "items": items,
            "total": summary["pending"],
            "page": 1,
            "pageSize": size,
            "hasMore": summary["pending"] > len(items),
        },
        "messages": {
            "unread": int((messages or {}).get("unread") or 0),
            "pendingAck": int((messages or {}).get("pendingAck") or 0),
        },
    }
