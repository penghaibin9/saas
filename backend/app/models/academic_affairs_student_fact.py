"""Stage C1: temporal academic identity facts for historical replay."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, PKMixin, TenantMixin


class StudentAcademicFact(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """A student's effective-dated academic identity.

    ``StudentProfile`` remains the current projection for hot-path reads. Historical
    reads must resolve this ledger by ``as_of`` instead of reading today's profile.
    Facts are append-oriented: a transition only closes the current row's
    ``valid_to`` and inserts the next version.
    """

    __tablename__ = "t_aa_student_academic_fact"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", "version_no", name="uk_aa_student_fact_version"),
        Index("ix_aa_student_fact_asof", "tenant_id", "student_id", "valid_from", "valid_to"),
        Index("ix_aa_student_fact_active", "tenant_id", "student_id", "valid_to"),
    )

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime)

    student_status: Mapped[str] = mapped_column(String(50), nullable=False)
    college_id: Mapped[int | None] = mapped_column(BigInteger)
    major_id: Mapped[int | None] = mapped_column(BigInteger)
    class_id: Mapped[int | None] = mapped_column(BigInteger)
    grade: Mapped[str | None] = mapped_column(String(20))

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger)
    source_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, default="EXACT", comment="EXACT/DERIVED/INFERRED/UNKNOWN"
    )
