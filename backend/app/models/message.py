"""消息通知（冻结册模块15：t_unified_message；模板/渠道回执表后续批次）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class UnifiedMessage(PKMixin, TenantMixin, CommonMixin, Base):
    """t_unified_message 统一消息（站内通知；渠道下发回执见 t_message_channel_log，后续批次）。"""
    __tablename__ = "t_unified_message"

    receiver_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_module: Mapped[str | None] = mapped_column(String(50))
    source_biz_id: Mapped[int | None] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(String(2000))
    message_type: Mapped[str | None] = mapped_column(String(50), comment="TODO：类型枚举以 11 中心 §11.19 为准")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNREAD", comment="UNREAD/READ")
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))
