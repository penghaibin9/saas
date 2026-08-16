"""Append-only evidence frozen at every canonical internship placement."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, PKMixin, TenantMixin
from app.models.internship import InternshipRecord


class InternshipPlacementSnapshot(PKMixin, TenantMixin, AuditTimeMixin, Base):
    __tablename__ = "t_internship_placement_snapshot"
    __table_args__ = (
        UniqueConstraint("tenant_id", "record_id", "placement_seq", name="uk_intern_placement_snapshot_seq"),
        Index("ix_intern_placement_snapshot_record_time", "tenant_id", "record_id", "placement_at"),
        Index("ix_intern_placement_snapshot_position_time", "tenant_id", "position_id", "placement_at"),
    )

    record_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    placement_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    application_id: Mapped[int | None] = mapped_column(BigInteger)
    enterprise_decision_id: Mapped[int | None] = mapped_column(BigInteger)
    campaign_id: Mapped[int | None] = mapped_column(BigInteger)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    position_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_credit_code: Mapped[str | None] = mapped_column(String(50))
    position_title: Mapped[str] = mapped_column(String(200), nullable=False)
    position_category: Mapped[str | None] = mapped_column(String(50))
    work_location: Mapped[str | None] = mapped_column(String(200))
    work_address: Mapped[str | None] = mapped_column(String(300))
    work_content: Mapped[str | None] = mapped_column(Text)
    major_requirement: Mapped[str | None] = mapped_column(String(200))
    grade_requirement: Mapped[str | None] = mapped_column(String(100))
    salary_range: Mapped[str | None] = mapped_column(String(50))
    subsidy: Mapped[str | None] = mapped_column(String(50))
    remuneration_type: Mapped[str | None] = mapped_column(String(30))
    remuneration_amount: Mapped[float | None] = mapped_column(Float)
    remuneration_cycle: Mapped[str | None] = mapped_column(String(30))
    daily_hours: Mapped[float | None] = mapped_column(Float)
    weekly_hours: Mapped[float | None] = mapped_column(Float)
    shift_type: Mapped[str | None] = mapped_column(String(30))
    night_shift: Mapped[bool | None] = mapped_column(Boolean)
    overtime_allowed: Mapped[bool | None] = mapped_column(Boolean)
    rest_days: Mapped[str | None] = mapped_column(String(50))
    rest_days_per_week: Mapped[float | None] = mapped_column(Float)
    accommodation_provided: Mapped[bool | None] = mapped_column(Boolean)
    meal_provided: Mapped[bool | None] = mapped_column(Boolean)
    hazardous_flag: Mapped[bool | None] = mapped_column(Boolean)
    special_equipment: Mapped[str | None] = mapped_column(String(200))
    prohibited_reason: Mapped[str | None] = mapped_column(String(500))
    enterprise_mentor_name: Mapped[str | None] = mapped_column(String(100))
    rights_status: Mapped[str | None] = mapped_column(String(30))
    rights_rule_version: Mapped[str | None] = mapped_column(String(64))
    rights_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    position_version: Mapped[int] = mapped_column(Integer, nullable=False)
    position_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    placement_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    captured_by_user_id: Mapped[int | None] = mapped_column(BigInteger)


if not hasattr(InternshipRecord, "current_placement_snapshot_id"):
    InternshipRecord.current_placement_snapshot_id = mapped_column(
        BigInteger, nullable=True, comment="→ t_internship_placement_snapshot.id"
    )
