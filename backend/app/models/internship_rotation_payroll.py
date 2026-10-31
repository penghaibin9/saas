"""Yiyang C05 structured rotation and monthly payroll facts."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipRotation(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_rotation"
    __table_args__ = (
        UniqueConstraint("tenant_id", "internship_id", "rotation_seq", name="uk_ix_rotation_seq"),
        Index("ix_ix_rotation_student", "tenant_id", "student_id", "batch_id", "status", "is_deleted"),
    )

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    rotation_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    department_name: Mapped[str] = mapped_column(String(160), nullable=False)
    department_manager_name: Mapped[str | None] = mapped_column(String(100))
    mentor_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    mentor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="PLANNED",
        comment="PLANNED/ACTIVE/COMPLETED/CANCELLED",
    )
    student_self_evaluation: Mapped[str | None] = mapped_column(Text)
    student_self_rating: Mapped[int | None] = mapped_column(Integer)
    self_submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    theory_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    skill_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    mentor_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    score_rule_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    evaluator_name: Mapped[str | None] = mapped_column(String(100))
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime)
    evaluation_comment: Mapped[str | None] = mapped_column(String(1000))


class InternshipRotationProject(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_rotation_project"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rotation_id", "project_seq", name="uk_ix_rotation_project_seq"),
        Index("ix_ix_rotation_project_status", "tenant_id", "rotation_id", "status", "is_deleted"),
    )

    rotation_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    project_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    project_content: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="PLANNED",
        comment="PLANNED/IN_PROGRESS/COMPLETED/CANCELLED",
    )
    mentor_note: Mapped[str | None] = mapped_column(String(1000))


class InternshipPayrollStatement(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_payroll_statement"
    __table_args__ = (
        UniqueConstraint("tenant_id", "internship_id", "pay_month", name="uk_ix_payroll_month"),
        Index("ix_ix_payroll_student", "tenant_id", "student_id", "batch_id", "pay_month", "is_deleted"),
    )

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    pay_month: Mapped[str] = mapped_column(String(7), nullable=False, comment="YYYY-MM")
    agreed_salary_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    agreed_salary_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    current_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class InternshipPayrollVersion(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_payroll_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "statement_id", "revision_no", name="uk_ix_payroll_revision"),
        Index("ix_ix_payroll_current", "tenant_id", "statement_id", "is_current", "status", "is_deleted"),
    )

    statement_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    paid_on: Mapped[date | None] = mapped_column(Date)
    evidence_file_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    evidence_sha256: Mapped[str | None] = mapped_column(String(64))
    submit_note: Mapped[str | None] = mapped_column(String(500))
    correction_reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="SUBMITTED",
        comment="SUBMITTED/APPROVED/RETURNED/SUPERSEDED",
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_by_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(String(500))
