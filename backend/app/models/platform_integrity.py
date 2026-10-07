"""PLAT-A federated integrity exception read model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class IntegrityException(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_integrity_exception"

    exception_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="OPEN", index=True,
        comment="OPEN/ACKNOWLEDGED/RESOLVED/IGNORED",
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="HIGH")
    detector_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    detector_version: Mapped[str] = mapped_column(String(32), nullable=False, default="V1")
    module_code: Mapped[str | None] = mapped_column(String(64), index=True)
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    manifest_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    file_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str | None] = mapped_column(String(1000))
    evidence_json: Mapped[dict | None] = mapped_column(JSON)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)
    acknowledged_by: Mapped[int | None] = mapped_column(BigInteger)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[int | None] = mapped_column(BigInteger)
    ignored_at: Mapped[datetime | None] = mapped_column(DateTime)
    ignored_by: Mapped[int | None] = mapped_column(BigInteger)
    resolution_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uk_integrity_exception_fingerprint"),
        Index("ix_integrity_exception_queue", "tenant_id", "status", "severity", "id"),
        Index("ix_integrity_exception_subject", "tenant_id", "module_code", "subject_type", "subject_id", "id"),
        Index("ix_integrity_exception_detector", "tenant_id", "detector_code", "last_detected_at", "id"),
    )


__all__ = ["IntegrityException"]
