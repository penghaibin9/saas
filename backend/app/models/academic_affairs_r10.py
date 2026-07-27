"""R10 动态成绩项与教务统计快照模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AaGradeSchemeSnapshot(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_aa_grade_scheme_snapshot"
    __table_args__ = (
        UniqueConstraint("tenant_id", "grade_task_id", name="uk_aa_grade_scheme_task"),
        Index("ix_aa_grade_scheme_status", "tenant_id", "status"),
    )

    grade_task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    scheme_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scheme_json: Mapped[str] = mapped_column(Text, nullable=False)
    total_weight: Mapped[float] = mapped_column(Float, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", comment="DRAFT/LOCKED")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_by: Mapped[str | None] = mapped_column(String(100))


class AaGradeComponentScore(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_aa_grade_component_score"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "grade_task_id", "student_id", "component_code",
            name="uk_aa_grade_component_student",
        ),
        Index("ix_aa_grade_component_record", "tenant_id", "grade_record_id"),
        Index("ix_aa_grade_component_task", "tenant_id", "grade_task_id", "student_id"),
    )

    grade_task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    grade_record_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    component_code: Mapped[str] = mapped_column(String(40), nullable=False)
    component_name: Mapped[str] = mapped_column(String(80), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    weighted_score: Mapped[float] = mapped_column(Float, nullable=False)
    scheme_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AaStatsSnapshot(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_aa_stats_snapshot"
    __table_args__ = (
        Index("ix_aa_stats_snapshot_type", "tenant_id", "snapshot_type", "status"),
        Index("ix_aa_stats_snapshot_term", "tenant_id", "term_id", "generated_at"),
        Index("ix_aa_stats_snapshot_hash", "tenant_id", "payload_hash"),
    )

    snapshot_type: Mapped[str] = mapped_column(String(40), nullable=False, default="OVERVIEW")
    term_id: Mapped[int | None] = mapped_column(BigInteger)
    college_id: Mapped[int | None] = mapped_column(BigInteger)
    major_id: Mapped[int | None] = mapped_column(BigInteger)
    scope_json: Mapped[str] = mapped_column(Text, nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_as_of: Mapped[datetime | None] = mapped_column(DateTime)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    generated_by: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="FROZEN")


# 确保 Base.metadata.create_all 注册 R11 真实学期试点表。
from app.models.academic_affairs_r11 import (  # noqa: E402,F401
    AaSemesterPilot,
    AaSemesterPilotCheckpoint,
)
