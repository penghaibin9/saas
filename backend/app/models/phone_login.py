"""手机号登录的权威绑定与待核验候选。

联系方式仍留在原主档；这两张表只表达“可作为登录别名”的已验证号码及
导入/治理带来的候选，避免把电话簿数据误当认证因素。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class PhoneLoginBinding(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_user_phone_login_binding"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uk_phone_login_binding_user"),
        UniqueConstraint("tenant_id", "active_phone_lookup", name="uk_phone_login_binding_active_lookup"),
        Index("ix_phone_login_binding_lookup", "tenant_id", "active_phone_lookup"),
        CheckConstraint("version >= 0", name="ck_phone_binding_version"),
        CheckConstraint("(state = 'VERIFIED' AND active_phone_lookup IS NOT NULL AND phone_ciphertext IS NOT NULL) OR (state IN ('UNBOUND', 'REVOKED') AND active_phone_lookup IS NULL AND phone_ciphertext IS NULL)", name="ck_phone_binding_state"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="UNBOUND", server_default="UNBOUND")
    phone_ciphertext: Mapped[str | None] = mapped_column(String(500))
    active_phone_lookup: Mapped[str | None] = mapped_column(String(64))
    lookup_key_id: Mapped[str | None] = mapped_column(String(32))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_candidate_id: Mapped[int | None] = mapped_column(BigInteger)
    source_job_id: Mapped[int | None] = mapped_column(BigInteger)
    verification_method: Mapped[str | None] = mapped_column(String(64))
    recovery_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class PhoneLoginCandidate(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_user_phone_login_candidate"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uk_phone_login_candidate_user"),
        CheckConstraint("version >= 0", name="ck_phone_candidate_version"),
        CheckConstraint("state IN ('PENDING', 'CONFLICT', 'APPLIED', 'CLEARED')", name="ck_phone_candidate_state"),
        CheckConstraint("owner_type = 'SELF'", name="ck_phone_candidate_owner"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    candidate_phone_ciphertext: Mapped[str | None] = mapped_column(String(500))
    candidate_lookup: Mapped[str | None] = mapped_column(String(64), index=True)
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False, default="SELF")
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    source_kind: Mapped[str | None] = mapped_column(String(40))
    source_job_id: Mapped[int | None] = mapped_column(BigInteger)
    source_row_no: Mapped[int | None] = mapped_column(BigInteger)
