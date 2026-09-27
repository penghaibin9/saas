"""Student-editable internship profile facts.

School authority fields (name/student no/college/major/grade/class/status) are intentionally
absent. They are projected from canonical student/org tables at read/snapshot time.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class StudentInternshipProfile(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_student_profile"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", name="uk_intern_student_profile"),
        Index("ix_intern_student_profile_student", "tenant_id", "student_id", "is_deleted"),
    )

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_student_profile.id")
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    headline: Mapped[str | None] = mapped_column(String(120))
    self_intro: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[str | None] = mapped_column(Text)
    available_from: Mapped[date | None] = mapped_column(Date)
    available_until: Mapped[date | None] = mapped_column(Date)
    expected_locations_json: Mapped[list | None] = mapped_column(JSON)
    skill_tags_json: Mapped[list | None] = mapped_column(JSON)
    resume_template_code: Mapped[str] = mapped_column(String(50), nullable=False, default="INTERNSHIP_STANDARD_V1")


class StudentInternshipProfileItem(PKMixin, TenantMixin, CommonMixin, Base):
    """Student-entered internship experiences/evidence; school facts stay references/projections."""

    __tablename__ = "t_internship_student_profile_item"
    __table_args__ = (
        Index("ix_intern_profile_item_type", "tenant_id", "profile_id", "item_type", "is_deleted"),
        Index("ix_intern_profile_item_source", "tenant_id", "source_ref_type", "source_ref_id", "is_deleted"),
    )

    profile_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_internship_student_profile.id")
    item_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="SKILL_EVIDENCE/CERTIFICATE/PROJECT/PRACTICE/AWARD/PORTFOLIO",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    level: Mapped[str | None] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="STUDENT_ENTERED", comment="STUDENT_ENTERED/SCHOOL_FACT")
    source_ref_type: Mapped[str | None] = mapped_column(String(80))
    source_ref_id: Mapped[str | None] = mapped_column(String(100))
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="UNVERIFIED", comment="UNVERIFIED/VERIFIED/NOT_REQUIRED")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
