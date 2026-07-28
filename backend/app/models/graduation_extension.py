"""毕业设计扩展闭环：优秀成果认定与延期答辩。

两者不能用“成绩等级=优秀”或“二次答辩轮次”冒充：
- 优秀成果有独立提名、专业复核、学院终审发布证据；
- 延期答辩有学生申请、导师意见、专业复核、学院批准与重新排期证据。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class GraduationExcellentOutcome(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_excellent_outcome"
    __table_args__ = (
        UniqueConstraint("tenant_id", "gd_student_id", name="uk_gd_excellent_student"),
        Index("ix_gd_excellent_batch_status", "tenant_id", "batch_id", "status", "is_deleted"),
    )

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING_MAJOR",
        comment="PENDING_MAJOR/PENDING_COLLEGE/PUBLISHED/REJECTED/WITHDRAWN",
    )
    nomination_reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    evidence_json: Mapped[list | None] = mapped_column(JSON)
    grade_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    nominated_by: Mapped[str | None] = mapped_column(String(100))
    nominated_at: Mapped[datetime | None] = mapped_column(DateTime)
    major_review_comment: Mapped[str | None] = mapped_column(String(1000))
    major_reviewed_by: Mapped[str | None] = mapped_column(String(100))
    major_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    college_review_comment: Mapped[str | None] = mapped_column(String(1000))
    college_reviewed_by: Mapped[str | None] = mapped_column(String(100))
    college_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationDefenseDelay(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_defense_delay"
    __table_args__ = (
        UniqueConstraint("tenant_id", "active_key", name="uk_gd_delay_active"),
        Index("ix_gd_delay_batch_status", "tenant_id", "batch_id", "status", "is_deleted"),
    )

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    active_key: Mapped[str | None] = mapped_column(String(100), comment="active:<gd_student_id>；终态为空")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING_ADVISOR",
        comment="PENDING_ADVISOR/PENDING_MAJOR/PENDING_COLLEGE/APPROVED/SCHEDULED/REJECTED/CANCELLED",
    )
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    evidence_json: Mapped[list | None] = mapped_column(JSON)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    advisor_comment: Mapped[str | None] = mapped_column(String(1000))
    advisor_reviewed_by: Mapped[str | None] = mapped_column(String(100))
    advisor_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    major_comment: Mapped[str | None] = mapped_column(String(1000))
    major_reviewed_by: Mapped[str | None] = mapped_column(String(100))
    major_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    college_comment: Mapped[str | None] = mapped_column(String(1000))
    college_reviewed_by: Mapped[str | None] = mapped_column(String(100))
    college_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    planned_defense_date: Mapped[str | None] = mapped_column(String(50))
    defense_group_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
