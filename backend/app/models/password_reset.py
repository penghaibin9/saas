"""密码重置短信可靠投递作业。验证码和手机号只以密文短暂保存。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class PasswordResetSmsJob(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_password_reset_sms_job"
    __table_args__ = (
        UniqueConstraint("request_id", name="uk_password_reset_sms_request"),
        Index("ix_password_reset_sms_claim", "status", "next_retry_at", "lease_expires_at", "id"),
    )

    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    code_encrypted: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_by: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    provider_request_id: Mapped[str | None] = mapped_column(String(100))
    last_error: Mapped[str | None] = mapped_column(String(500))
