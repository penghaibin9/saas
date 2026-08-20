"""Machine-verifiable disaster-recovery run evidence.

Manual BackupEvidence/RestoreDrill records remain useful operator notes, but they
must never be sufficient to make the production DR health indicator green.
RecoveryRun is append-only authority populated by the deployment runner/CLI.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, PKMixin


class RecoveryRun(PKMixin, AuditTimeMixin, Base):
    __tablename__ = "t_recovery_run"

    run_id: Mapped[str] = mapped_column(String(100), nullable=False)
    run_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="BACKUP/RESTORE/PITR")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="MACHINE", comment="MACHINE only is health-eligible")
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="RUNNING/VERIFYING/PASSED/FAILED")
    backup_set_id: Mapped[str | None] = mapped_column(String(160), index=True)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_commit: Mapped[str | None] = mapped_column(String(64))
    runner_id: Mapped[str | None] = mapped_column(String(160))
    rpo_seconds: Mapped[int | None] = mapped_column(BigInteger)
    rto_seconds: Mapped[int | None] = mapped_column(BigInteger)
    target_rpo_seconds: Mapped[int | None] = mapped_column(BigInteger)
    target_rto_seconds: Mapped[int | None] = mapped_column(BigInteger)
    assertions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    __table_args__ = (
        UniqueConstraint("run_id", name="uk_recovery_run_id"),
        UniqueConstraint("evidence_sha256", name="uk_recovery_run_evidence_sha"),
    )
