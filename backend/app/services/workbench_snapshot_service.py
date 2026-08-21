"""教师工作台只读快照：一次鉴权后聚合摘要、分类、最近待办和消息角标。

不改变权限口径，复用 workbench_todo_service 的 SQL 可见性条件；不缓存敏感明细，
仅减少前端重复请求、重复范围解析和数据库会话创建。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session
from app.services import workbench_todo_service as todo_svc


_ALLOWED_CLIENTS = {"pc", "teacherMini"}


def snapshot(user: dict, page_size: int = 8, *, client: str = "pc") -> dict:
    from app.models import UnifiedTodo
    from app.services import approval_runtime_service, message_center_service as message_svc

    if client not in _ALLOWED_CLIENTS:
        raise AppException("VALIDATION_ERROR", "不支持的工作台客户端")

    size = max(1, min(20, int(page_size or 8)))

    with session() as db:
        visibility = todo_svc._visibility_cond(db, user)
        if visibility is None:
            todo_pending = 0
            by_type = {}
            items = []
        else:
            base = [
                UnifiedTodo.tenant_id == _tid(),
                UnifiedTodo.is_deleted.is_(False),
                visibility,
            ]
            pending = UnifiedTodo.status == "PENDING"
            todo_pending = int(db.scalar(select(func.count()).where(*base, pending)) or 0)
            type_rows = db.execute(select(UnifiedTodo.todo_type, func.count())
                                   .where(*base, pending)
                                   .group_by(UnifiedTodo.todo_type)).all()
            by_type = {todo_type: int(count) for todo_type, count in type_rows}
            rows = db.scalars(select(UnifiedTodo).where(*base, pending)
                              .order_by(UnifiedTodo.due_at.is_(None).asc(),
                                        UnifiedTodo.due_at.asc(), UnifiedTodo.id.desc())
                              .limit(size)).all()
            items = [todo_svc._todo_dict(item, client=client) for item in rows]

    # TP-W03：pending/overdue/nearDeadline/doneToday 这组磁贴在前端全部下钻到 Approval 页
    # （/admin/approval/todos、/admin/approval/done）。这组页面读的是 WorkflowTask，不是
    # UnifiedTodo——如果数字继续来自 UnifiedTodo 聚合（还混进 AA_GRADE_ENTRY 等非审批待办类
    # 型），点开卡片经常看不到与卡片数字对应的行，甚至看到空列表。数字与目标必须同一个
    # Authority，直接复用 Approval 中心自己的 summary()，不在这里重复一份口径。
    # UnifiedTodo 聚合（todo_pending / by_type / items）仍然是页面内嵌"最近待办"小组件与
    # 分类磁贴（typeCue，各自跳到真实业务域页面）的正确数据源，两者不是同一件事。
    approval_summary = approval_runtime_service.summary(user=user)
    summary = {
        "pending": int(approval_summary.get("total") or 0),
        "overdue": int(approval_summary.get("overdue") or 0),
        "nearDeadline": int(approval_summary.get("nearDeadline") or 0),
        "doneToday": int(approval_summary.get("doneToday") or 0),
    }

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
        "count": {"total": todo_pending, "byType": by_type},
        "todos": {
            "items": items,
            "total": todo_pending,
            "page": 1,
            "pageSize": size,
            "hasMore": todo_pending > len(items),
        },
        "messages": {
            "unread": int((messages or {}).get("unread") or 0),
            "pendingAck": int((messages or {}).get("pendingAck") or 0),
        },
    }
