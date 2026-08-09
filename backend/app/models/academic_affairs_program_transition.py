"""Stage C1: program transition assessments created by academic-fact major changes."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, PKMixin, TenantMixin


class ProgramTransitionAssessment(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """Evidence of how a major change affects the student's program binding.

    This is deliberately not a StudentProgramInstance or requirement engine. It records
    the source fact/version, candidate program bindings and the deterministic decision
    available at transition time. Missing/ambiguous bindings are explicit MANUAL_REVIEW,
    never silently guessed.
    """

    __tablename__ = "t_aa_program_transition_assessment"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "student_id", "source_type", "source_ref_id", "source_fact_version",
            name="uk_aa_program_transition_source",
        ),
        Index("ix_aa_program_transition_student", "tenant_id", "student_id", "assessed_at"),
        Index("ix_aa_program_transition_status", "tenant_id", "assessment_status"),
    )

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_fact_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_fact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_fact_id: Mapped[int | None] = mapped_column(BigInteger)

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger)
    from_major_id: Mapped[int | None] = mapped_column(BigInteger)
    to_major_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_class_id: Mapped[int | None] = mapped_column(BigInteger)
    grade: Mapped[str | None] = mapped_column(String(20))

    from_program_id: Mapped[int | None] = mapped_column(BigInteger)
    target_program_id: Mapped[int | None] = mapped_column(BigInteger)
    decision: Mapped[str] = mapped_column(
        String(40), nullable=False, comment="SWITCH_TARGET/MANUAL_REVIEW"
    )
    assessment_status: Mapped[str] = mapped_column(
        String(40), nullable=False,
        comment="READY/NO_TARGET_BINDING/AMBIGUOUS_TARGET/APPLIED/APPLIED_REVIEW_REQUIRED",
    )
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
