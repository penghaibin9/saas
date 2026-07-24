"""幂等持久化记录（Redis 不可用时的关键写路径兜底）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TenantMixin


class IdempotencyRecord(PKMixin, TenantMixin, Base):
    __tablename__ = "t_idempotency_record"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "operation", "key_hash",
                         name="uk_idempotency_tenant_user_op_key"),
        Index("ix_idempotency_expires", "expires_at"),
    )

    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="PROCESSING")
    result_json: Mapped[dict | None] = mapped_column(JSON)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
