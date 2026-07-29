"""R11 真实学校完整学期试点模型。

试点只绑定当前租户内的正式学期。检查结果来自真实业务表，禁止把 seed、mock 或测试通过
直接写成 COMPLETED。每次检查保留六阶段证据与哈希，完成状态只能由全部阶段通过后显式确认。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AaSemesterPilot(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_aa_semester_pilot"
    __table_args__ = (
        UniqueConstraint("tenant_id", "term_id", name="uk_aa_semester_pilot_term"),
        Index("ix_aa_semester_pilot_status", "tenant_id", "status"),
    )

    term_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    term_code: Mapped[str] = mapped_column(String(40), nullable=False)
    pilot_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PREPARING",
        comment="PREPARING/BLOCKED/RUNNING/READY_TO_COMPLETE/COMPLETED/CANCELLED",
    )
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    real_data_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    check_run_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_stage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_evidence_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    latest_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_by: Mapped[str | None] = mapped_column(String(100))
    completion_note: Mapped[str | None] = mapped_column(String(500))


class AaSemesterPilotCheckpoint(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_aa_semester_pilot_checkpoint"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "pilot_id", "run_no", "stage_code",
            name="uk_aa_semester_pilot_checkpoint",
        ),
        Index("ix_aa_semester_checkpoint_pilot", "tenant_id", "pilot_id", "run_no"),
        Index("ix_aa_semester_checkpoint_stage", "tenant_id", "stage_code", "passed"),
        Index("ix_aa_semester_checkpoint_hash", "tenant_id", "evidence_hash"),
    )

    pilot_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    run_no: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_code: Mapped[str] = mapped_column(String(32), nullable=False)
    stage_name: Mapped[str] = mapped_column(String(80), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conclusion: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    checked_by: Mapped[str | None] = mapped_column(String(100))
