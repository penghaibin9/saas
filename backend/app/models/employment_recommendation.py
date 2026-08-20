"""Teacher V3 T7 first-class employment recommendation fact.

A recommendation is not a follow-up row.  It has its own stable identity, job/student/teacher
provenance and outcome lifecycle; EmpFollowup may only be written as a secondary audit-friendly
side effect by the recommendation command.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class EmpRecommendation(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_emp_recommendation"
    __table_args__ = (
        Index("ix_emp_reco_student_status", "tenant_id", "emp_student_id", "status", "is_deleted"),
        Index("ix_emp_reco_job_status", "tenant_id", "job_id", "status", "is_deleted"),
        Index("ix_emp_reco_teacher_time", "tenant_id", "teacher_user_id", "recommended_at", "id"),
    )

    emp_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    student_profile_id: Mapped[int | None] = mapped_column(BigInteger)
    job_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    teacher_user_id: Mapped[int | None] = mapped_column(BigInteger)
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    company_name_snapshot: Mapped[str | None] = mapped_column(String(200))
    job_title_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="RECOMMENDED")
    outcome: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    outcome_note: Mapped[str | None] = mapped_column(String(500))
    recommended_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
