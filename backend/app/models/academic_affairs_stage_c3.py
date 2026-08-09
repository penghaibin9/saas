"""Stage C3 immutable graduation / archive facts.

These tables deliberately separate historical facts from the existing mutable UI
projections. ``AaGraduationAuditResult`` remains the current work-queue projection,
while every formal evaluation/decision is append-only here. ``AaArchiveBatch`` remains
the operational batch projection, while every successful archive/correction produces
an immutable manifest version.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class GraduationEvaluationRun(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """One immutable formal graduation evaluation for one student.

    Re-running a precheck MUST insert Run#N+1 instead of overwriting Run#N. The
    mutable result row may point to/project the newest run for compatibility, but the
    evidence used for a historical decision stays reproducible here.
    """

    __tablename__ = "t_aa_graduation_evaluation_run"
    __table_args__ = (
        UniqueConstraint("tenant_id", "result_id", "run_no", name="uk_aa_grad_eval_run"),
        Index("ix_aa_grad_eval_student", "tenant_id", "batch_id", "student_id", "run_no"),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    result_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    run_no: Mapped[int] = mapped_column(Integer, nullable=False)
    program_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    input_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    item_results_json: Mapped[str] = mapped_column(Text, nullable=False)
    overall: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    evaluator_version: Mapped[str] = mapped_column(String(50), nullable=False, default="STAGE_C3_V1")


class GraduationDecisionFact(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """Immutable versioned graduation decision referencing the exact evaluation run.

    Ordinary finalisation creates Decision#1. A legal post-archive correction may append
    Decision#2+ with ``supersedes_id`` and ``correction_case_id``; Decision#1 is never
    overwritten or deleted. This is required for the 138/140 -> corrected grade ->
    re-evaluation -> new graduation decision replay chain.
    """

    __tablename__ = "t_aa_graduation_decision_fact"
    __table_args__ = (
        UniqueConstraint("tenant_id", "result_id", "decision_no", name="uk_aa_grad_decision_version"),
        UniqueConstraint("tenant_id", "correction_case_id", name="uk_aa_grad_decision_correction_case"),
        Index("ix_aa_grad_decision_eval", "tenant_id", "evaluation_run_id"),
        Index("ix_aa_grad_decision_latest", "tenant_id", "result_id", "decision_no"),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    result_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    decision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evaluation_run_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    conclusion: Mapped[str] = mapped_column(String(50), nullable=False)
    supersedes_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    correction_case_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    decision_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    decision_by: Mapped[int | None] = mapped_column(BigInteger)
    review_note: Mapped[str | None] = mapped_column(String(500))


class ArchiveManifest(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """Versioned immutable archive manifest; V2 supersedes V1, never mutates it."""

    __tablename__ = "t_aa_archive_manifest"
    __table_args__ = (
        UniqueConstraint("tenant_id", "archive_batch_id", "version_no", name="uk_aa_archive_manifest_version"),
        Index("ix_aa_archive_manifest_latest", "tenant_id", "archive_batch_id", "version_no"),
    )

    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    archive_batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    domain_counts_json: Mapped[str] = mapped_column(Text, nullable=False)
    domain_hashes_json: Mapped[str] = mapped_column(Text, nullable=False)
    max_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    supersedes_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    archived_by: Mapped[int | None] = mapped_column(BigInteger)


class PostArchiveCorrectionCase(PKMixin, TenantMixin, CommonMixin, Base):
    """The only formal write-after-ARCHIVED workflow.

    Stage C3 deliberately limits the first production scope to ``GRADE`` and
    ``GRADUATION``. Applying a case appends a new official domain fact and a new
    ArchiveManifest version; it never reopens the archived term. ``official_fact_*``
    closes the evidence chain from the correction workflow row to the exact fact it
    produced.
    """

    __tablename__ = "t_aa_post_archive_correction_case"
    __table_args__ = (
        UniqueConstraint("tenant_id", "archive_batch_id", "correction_no", name="uk_aa_archive_correction_no"),
        Index("ix_aa_archive_correction_status", "tenant_id", "archive_batch_id", "status"),
    )

    archive_batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    correction_no: Mapped[int] = mapped_column(Integer, nullable=False)
    business_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="GRADE/GRADUATION")
    target_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correction_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_manifest: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="HIGH")
    second_approved_by: Mapped[int | None] = mapped_column(BigInteger)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    official_fact_type: Mapped[str | None] = mapped_column(String(50))
    official_fact_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    resulting_manifest_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING_SECOND_APPROVAL", index=True,
        comment="PENDING_SECOND_APPROVAL/APPLIED/REJECTED",
    )
