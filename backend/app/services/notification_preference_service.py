"""消息通知分类偏好：按人+分类开关，供 mobile_student_service.my_messages()/
mobile_teacher_service.messages() 聚合读取时真实生效过滤（不做纯客户端假开关）。
未建行的分类默认视为开启，与产品默认"全部接收"一致。"""
from __future__ import annotations

from sqlalchemy import select

from app.services.db_service import _tid, session

STUDENT_CATEGORIES = [
    {"key": "todo", "label": "待办提醒"},
    {"key": "notice", "label": "通知公告"},
    {"key": "progress", "label": "服务进度"},
]
TEACHER_CATEGORIES = [
    {"key": "system", "label": "系统通知"},
    {"key": "dynamic", "label": "学生动态"},
    {"key": "risk", "label": "风险预警"},
]


def _user_key(user) -> str:
    return str((user or {}).get("userId") or "")


def get_preferences(user, categories) -> dict:
    uk = _user_key(user)
    with session() as db:
        from app.models import NotificationPreference
        rows = db.scalars(select(NotificationPreference).where(
            NotificationPreference.tenant_id == _tid(), NotificationPreference.user_key == uk,
            NotificationPreference.is_deleted.is_(False))).all()
        overrides = {r.category: bool(r.enabled) for r in rows}
        return {"items": [{"key": c["key"], "label": c["label"],
                           "enabled": overrides.get(c["key"], True)} for c in categories]}


def set_preference(user, category, enabled) -> dict:
    uk = _user_key(user)
    with session() as db:
        from app.models import NotificationPreference
        row = db.scalars(select(NotificationPreference).where(
            NotificationPreference.tenant_id == _tid(), NotificationPreference.user_key == uk,
            NotificationPreference.category == category)).first()
        if row:
            row.enabled = bool(enabled)
            row.is_deleted = False
        else:
            row = NotificationPreference(tenant_id=_tid(), user_key=uk, category=category,
                                         enabled=bool(enabled))
            db.add(row)
        db.commit()
        return {"key": category, "enabled": bool(enabled)}


def enabled_categories(user, all_categories) -> set:
    """返回当前用户"已开启"的分类 key 集合；未设置过的分类默认开启。"""
    uk = _user_key(user)
    with session() as db:
        from app.models import NotificationPreference
        rows = db.scalars(select(NotificationPreference).where(
            NotificationPreference.tenant_id == _tid(), NotificationPreference.user_key == uk,
            NotificationPreference.is_deleted.is_(False))).all()
        overrides = {r.category: bool(r.enabled) for r in rows}
    return {c for c in all_categories if overrides.get(c, True)}
