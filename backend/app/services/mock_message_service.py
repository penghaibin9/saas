"""mock 消息服务。字段对齐 docs/api/04 §4.13（t_unified_message）。"""
from __future__ import annotations

from app.core.response import paginate

_MESSAGES = [
    {"messageId": "msg_9001", "title": "您有一条实习周报待批阅", "messageType": "TODO_NOTICE",
     "sourceModule": "internship", "readStatus": "UNREAD", "urgent": False,
     "actionUrl": "/intern/reports/rp_3007", "createdAt": "2026-07-04T08:30:00+08:00"},
    {"messageId": "msg_9002", "title": "教务处发布：期末实习总结提交通知", "messageType": "ANNOUNCEMENT",
     "sourceModule": "core", "readStatus": "UNREAD", "urgent": True,
     "actionUrl": "/announcements/an_77", "createdAt": "2026-07-03T16:10:00+08:00"},
    {"messageId": "msg_9003", "title": "系统：您的身份「实习导师」权限已更新", "messageType": "SYSTEM",
     "sourceModule": "authz", "readStatus": "READ", "urgent": False,
     "actionUrl": "/profile/roles", "createdAt": "2026-07-02T10:00:00+08:00"},
]


def list_messages(read_status: str | None = None, message_type: str | None = None,
                  page: int = 1, page_size: int = 20) -> dict:
    from app.db.session import db_enabled
    if db_enabled():
        from app.services import db_service
        items, total = db_service.list_messages(read_status, message_type, page, page_size)
        data = paginate(items, total, page, page_size)
        data["unread"] = sum(1 for r in items if r["readStatus"] == "UNREAD")
        return data
    rows = _MESSAGES
    if read_status:
        rows = [r for r in rows if r["readStatus"] == read_status]
    if message_type:
        rows = [r for r in rows if r["messageType"] == message_type]
    total = len(rows)
    start = (page - 1) * page_size
    data = paginate(rows[start:start + page_size], total, page, page_size)
    data["unread"] = sum(1 for r in _MESSAGES if r["readStatus"] == "UNREAD")
    return data


def mark_read(message_id: str) -> dict:
    """标记已读：DB 模式写 t_unified_message.status=READ + read_at。"""
    from app.db.session import db_enabled
    if db_enabled():
        from app.services import db_service
        return db_service.message_read(message_id)
    return {"messageId": message_id, "status": "READ"}
