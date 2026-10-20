"""Teacher PC overview: an academic-only projection of the canonical todo audience.

No task creation/completion and no menu-derived counts. The shared todo service
continues to own audience and typed routes; this read adds SQL domain/search paging.
"""
from datetime import timedelta

from sqlalchemy import func, select

from app.models import UnifiedTodo
from app.services import workbench_todo_service as todo_service
from app.services.db_service import _iso, _tid, session


def role_queue(user, *, status="PENDING", keyword="", page=1, page_size=20):
    with session() as db:
        visible = todo_service._visibility_cond(db, user)
        uid = todo_service._uid(user)
        now = todo_service._utc_now()
        base = [UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False),
                UnifiedTodo.source_module == "academic-affairs"]
        # Invalid identity cannot fall back to the tenant's shared responsibility pool.
        base.append(visible if visible is not None and uid > 0 else UnifiedTodo.id < 0)
        summary = {"pending": 0, "nearDeadline": 0, "done": 0,
                   "toStart": None, "initiated": None}

        def count(*conditions):
            return int(db.scalar(select(func.count()).select_from(UnifiedTodo)
                                 .where(*base, *conditions)) or 0)

        summary["pending"] = count(UnifiedTodo.status == "PENDING")
        summary["nearDeadline"] = count(UnifiedTodo.status == "PENDING",
                                        UnifiedTodo.due_at >= now,
                                        UnifiedTodo.due_at <= now + timedelta(hours=24))
        summary["done"] = count(UnifiedTodo.status == "DONE", UnifiedTodo.assignee_id == uid)
        conditions = [*base, UnifiedTodo.status == status]
        if status == "DONE":
            conditions.append(UnifiedTodo.assignee_id == uid)
        if keyword.strip():
            conditions.append(UnifiedTodo.title.contains(keyword.strip(), autoescape=True))
        total = int(db.scalar(select(func.count()).select_from(UnifiedTodo).where(*conditions)) or 0)
        rows = db.scalars(select(UnifiedTodo).where(*conditions)
                          .order_by(UnifiedTodo.due_at.is_(None).asc(), UnifiedTodo.due_at.asc(),
                                    UnifiedTodo.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        items = []
        for row in rows:
            item = todo_service._todo_dict(row, client="pc")
            item.update({
                "assigneeId": str(row.assignee_id),
                "responsibility": "明确指派给本人" if row.assignee_id == uid else "授权范围内责任池",
                "assignmentReason": "正式待办指派给当前账号" if row.assignee_id == uid
                else "正式待办位于当前账号可见学生范围的责任池",
                # A todo has no authoritative domain blocker/next-assignee columns.
                "blocker": None,
                "completedAt": _iso(row.completed_at) if row.completed_at else None,
            })
            items.append(item)
        return {
            "items": items, "total": total, "page": page, "pageSize": page_size,
            "summary": summary, "sourceTime": _iso(now), "scopeBlocked": uid <= 0,
            "scopeNote": "仅教务正式待办：本人指派及授权责任池。待办没有统一学期字段，不随运行检查学期筛选。",
            "capabilities": {"pending": True, "done": True, "toStart": False, "initiated": False},
            "unavailableReason": "尚无统一的待启动条件和发起人投影，请进入各业务工作区查看正式记录。",
        }
