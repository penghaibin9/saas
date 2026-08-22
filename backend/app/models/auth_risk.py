"""Authentication risk/challenge state shared by all workers.

The control-plane auth P0 deliberately keeps these records outside tenant business
models: login risk exists before authentication, and platform identities may not
belong to a school tenant.  Keys are irreversible hashes; no login name, password
or raw IP is stored here.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin


class AuthRiskState(PKMixin, CommonMixin, Base):
    __tablename__ = "t_auth_risk_state"

    risk_type: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("risk_type", "risk_key_hash", name="uk_auth_risk_type_key"),
        Index("ix_auth_risk_expiry", "risk_type", "expires_at", "id"),
        Index("ix_auth_risk_tenant_lock", "tenant_id", "locked_until", "id"),
    )


class AuthChallengeState(PKMixin, Base):
    """One-time captcha state for strict environments when Redis is unavailable.

    ``payload_json`` contains only HMAC/digest bindings produced by
    ``auth_challenge_service``; the answer itself is never stored in plaintext.
    ``consumed_at`` is updated under a row lock, making one challenge single-use
    across workers and restarts.
    """

    __tablename__ = "t_auth_challenge_state"

    challenge_id_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
