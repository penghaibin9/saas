"""学生 PC 门户 · 消息通知 PC 视图。

复用 mobile_student_service 的本人消息中心（严格本人可见）+ 标记已读 + 通知偏好；
PC 视图在其扁平 list 上做分页。均为本人数据，不返回全校消息。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import mobile_student_service as stu


def inbox(user: dict, page: int = 1, page_size: int = 20) -> dict:
    """消息中心 PC 分页视图（复用 my_messages 的本人聚合，对扁平 list 分页）。"""
    try:
        page = max(1, int(page))
        page_size = min(100, max(1, int(page_size)))
    except (TypeError, ValueError):
        page, page_size = 1, 20
    data = stu.my_messages(user)  # {hasData, unreadCount, tabs, groups, list}
    items = list(data.get("list") or [])
    total = len(items)
    start = (page - 1) * page_size
    paged = items[start:start + page_size]
    return {**data, "list": paged, "page": page, "pageSize": page_size, "total": total}


def mark_read(user: dict, message_id) -> dict:
    """标记本人某条消息为已读（非本人 404，不泄露存在性）。"""
    return stu.message_mark_read(user, message_id)


def get_preferences(user: dict) -> dict:
    return stu.notify_preferences(user)


def set_preference(user: dict, body: dict) -> dict:
    return stu.notify_set_preference(user, body or {})
