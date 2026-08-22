"""Control-plane tenant offboarding/destruction workflow models.

Tenant.status remains the hard operating state.  Long-running offboarding is a
separate control-plane job so retention, legal hold, retries and purge evidence
are never compressed into one destructive DELETE.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin


class TenantOffboardingJob(PKMixin, CommonMixin, Base):
    __tablename__ = "t_tenant_offboarding_job"

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    requested_by: Mapped[int | None] = mapped_column(BigInteger)
    approved_by: Mapped[int | None] = mapped_column(BigInteger)
    expected_tenant_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    final_export_sha256: Mapped[str | None] = mapped_column(String(64))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    legal_hold_blocked: Mapped[bool] = mapped_column(nullable=False, default=False)
    purge_evidence_sha256: Mapped[str | None] = mapped_column(String(64))
    preview_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class TenantOffboardingStep(PKMixin, CommonMixin, Base):
    __tablename__ = "t_tenant_offboarding_step"

    job_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    step_code: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("job_id", "step_code", name="uk_tenant_offboarding_step"),
    )


class TenantTombstone(PKMixin, AuditTimeMixin, Base):
    __tablename__ = "t_tenant_tombstone"

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    tenant_code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    offboarding_job_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    final_export_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    purge_evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    purged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
