"""通用用户偏好（按人 + 偏好键的 KV）。

与 t_notification_preference 的区别：那张表是消息分类专用（category 取值锁死、只有 bool enabled、
无 value 字段），语义不可复用。本表是通用 KV，首个用途是「新手引导是否已看过」——
存后端而非 localStorage，保证老师换一台电脑/清缓存后不会被重复弹引导。

pref_key 命名约定：<域>.<用途>，如 guide.graduation.gd-batches。
pref_value 存字符串；需要结构化时存 JSON 文本，由调用方自行解析。
"""
from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class UserPreference(PKMixin, TenantMixin, CommonMixin, Base):
    """t_user_preference 通用用户偏好 KV。"""
    __tablename__ = "t_user_preference"
    __table_args__ = (UniqueConstraint("tenant_id", "user_key", "pref_key", name="uk_user_pref"),)

    user_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True,
                                          comment="当前用户标识（userId，含 db-/u_ 前缀原样存）")
    pref_key: Mapped[str] = mapped_column(String(100), nullable=False,
                                          comment="偏好键，约定 <域>.<用途>，如 guide.graduation.gd-batches")
    pref_value: Mapped[str] = mapped_column(String(500), nullable=False, default="",
                                            comment="偏好值；结构化数据存 JSON 文本")
