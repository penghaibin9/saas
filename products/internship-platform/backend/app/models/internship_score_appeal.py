"""Standalone 岗位实习成绩申诉模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipScoreAppeal(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_score_appeal"
    __table_args__ = (
        Index(
            "ix_score_appeal_record_status",
            "tenant_id", "internship_id", "status", "id",
        ),
        Index(
            "ix_score_appeal_student",
            "tenant_id", "student_id", "id",
        ),
    )

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    score_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(80), nullable=False, default="INTERNSHIP_SCORE_APPEAL")
    wo_type: Mapped[str] = mapped_column(String(30), nullable=False, default="COMPLAINT")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="HIGH")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_HANDLE")
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    handler: Mapped[str | None] = mapped_column(String(100))
    trail_json: Mapped[list | None] = mapped_column(JSON)
    close_time: Mapped[datetime | None] = mapped_column(DateTime)
