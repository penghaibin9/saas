"""Yiyang C08/G15 report quality facts.

Report rules are configurable by internship batch. Submission versions and review facts are
append-only so a returned/resubmitted report cannot erase the evidence that was previously
submitted and reviewed.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class InternshipReportRuleConfig(PKMixin, TenantMixin, CommonMixin, Base):
    """Per-batch report rules. Missing rows use service defaults; no hidden hard-coded UI truth."""
    __tablename__ = "t_internship_report_rule_config"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_id", name="uk_ix_report_rule_batch"),
        Index("ix_ix_report_rule_batch_active", "tenant_id", "batch_id", "is_deleted"),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    weekly_min_words: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    plan_task_min_words: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    monthly_min_words: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    summary_min_words: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    max_images: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    max_videos: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    remark: Mapped[str | None] = mapped_column(String(500))


class InternshipReportVersion(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """Immutable student submission snapshot.

    No CommonMixin/is_deleted/version: this table is historical evidence and is never edited or
    soft-deleted in normal business flows.
    """
    __tablename__ = "t_internship_report_version"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "report_kind", "report_id", "version_no",
            name="uk_ix_report_snapshot_version",
        ),
        Index(
            "ix_ix_report_snapshot_lookup",
            "tenant_id", "report_kind", "report_id", "version_no",
        ),
        Index(
            "ix_ix_report_snapshot_internship",
            "tenant_id", "internship_id", "student_id", "submitted_at",
        ),
    )

    report_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="WEEKLY/PROCESS")
    report_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    report_type: Mapped[str | None] = mapped_column(
        String(20), comment="PROCESS: DAILY/MONTHLY/SUMMARY; WEEKLY 留空")
    period_key: Mapped[str | None] = mapped_column(String(32))
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    attachment_file_ids_json: Mapped[list | None] = mapped_column(JSON)
    attachment_meta_json: Mapped[list | None] = mapped_column(JSON)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class InternshipReportReview(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """Immutable teacher review tied to one exact submission version."""
    __tablename__ = "t_internship_report_review"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "report_version_id", name="uk_ix_report_version_review"),
        Index(
            "ix_ix_report_review_lookup",
            "tenant_id", "report_kind", "report_id", "reviewed_at",
        ),
    )

    report_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    report_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    report_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False, comment="APPROVE/RETURN")
    rating_level: Mapped[int | None] = mapped_column(
        Integer, comment="五级评价：1~5；旧客户端兼容可空")
    summary_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2), comment="仅实习总结可填 0~100")
    comment: Mapped[str | None] = mapped_column(Text)
    reviewer_user_id: Mapped[str | None] = mapped_column(String(64))
    reviewer_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
