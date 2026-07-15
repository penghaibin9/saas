"""消息通知分类偏好（移动端首创）。按人+分类开关，聚合读取(me/messages、teacher/messages)时真实生效过滤，
不做纯客户端假开关。未建行的分类默认视为开启（enabled=True），与产品默认"全部接收"一致。"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class NotificationPreference(PKMixin, TenantMixin, CommonMixin, Base):
    """t_notification_preference 通知分类开关。"""
    __tablename__ = "t_notification_preference"
    __table_args__ = (UniqueConstraint("tenant_id", "user_key", "category", name="uk_notify_pref"),)

    user_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True,
                                          comment="当前用户标识（userId，含 db-/u_ 前缀原样存）")
    category: Mapped[str] = mapped_column(String(30), nullable=False,
                                          comment="学生:todo/notice/progress；教师:system/dynamic/risk")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
