"""Yiyang C08/G16 teacher execution facts and emergency notice facts."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipTeacherCheckin(PKMixin, TenantMixin, CommonMixin, Base):
    """Teacher's own check-in. Never reuse student check-in facts."""
    __tablename__ = "t_internship_teacher_checkin"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "batch_id", "teacher_user_id", "local_date",
            name="uk_ix_teacher_checkin_day",
        ),
        Index(
            "ix_ix_teacher_checkin_batch_teacher",
            "tenant_id", "batch_id", "teacher_user_id", "local_date",
        ),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    checked_in_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    accuracy_m: Mapped[float | None] = mapped_column(Numeric(10, 2))
    address: Mapped[str | None] = mapped_column(String(500))
    note: Mapped[str | None] = mapped_column(String(500))


class InternshipTeacherWorkReport(PKMixin, TenantMixin, CommonMixin, Base):
    """Teacher's own daily internship work report."""
    __tablename__ = "t_internship_teacher_work_report"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "batch_id", "teacher_user_id", "report_date",
            name="uk_ix_teacher_work_report_day",
        ),
        Index(
            "ix_ix_teacher_work_report_batch_teacher",
            "tenant_id", "batch_id", "teacher_user_id", "report_date",
        ),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    work_content: Mapped[str] = mapped_column(Text, nullable=False)
    issue_content: Mapped[str | None] = mapped_column(Text)
    next_plan: Mapped[str | None] = mapped_column(Text)
    student_count: Mapped[int | None] = mapped_column(Integer)
    attachment_file_ids_json: Mapped[list | None] = mapped_column(JSON)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class InternshipEmergencyNotice(PKMixin, TenantMixin, CommonMixin, Base):
    """School emergency notice fact. Student re-login reads this persisted row."""
    __tablename__ = "t_internship_emergency_notice"
    __table_args__ = (
        Index(
            "ix_ix_emergency_notice_batch_published",
            "tenant_id", "batch_id", "published_at", "id",
        ),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sender_user_id: Mapped[int | None] = mapped_column(BigInteger)
    sender_name_snapshot: Mapped[str | None] = mapped_column(String(100))
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PUBLISHED",
        comment="PUBLISHED/WITHDRAWN")
    outbox_id: Mapped[int | None] = mapped_column(BigInteger)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    withdraw_reason: Mapped[str | None] = mapped_column(String(500))
