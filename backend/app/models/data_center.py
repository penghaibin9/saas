"""A4 / P0-06 数据驾驶舱：专题报表配置与发布版本真值。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class DataCenterReport(PKMixin, TenantMixin, CommonMixin, Base):
    """专题报表当前工作副本；发布历史由 DataCenterReportVersion append-only 冻结。"""

    __tablename__ = "t_data_center_report"
    __table_args__ = (
        UniqueConstraint("tenant_id", "report_no", name="uk_dc_report_no"),
        Index("ix_dc_report_tenant_status_updated", "tenant_id", "status", "updated_at"),
    )

    report_no: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="ACADEMIC")
    cycle: Mapped[str] = mapped_column(String(30), nullable=False, default="MONTHLY")
    scope_name: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    caliber_code: Mapped[str] = mapped_column(String(40), nullable=False, default="REGISTERED")
    query_json: Mapped[dict | None] = mapped_column(JSON)
    layout_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    owner_id: Mapped[str | None] = mapped_column(String(100))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    published_version_no: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    void_reason: Mapped[str | None] = mapped_column(String(500))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime)
    voided_by_name: Mapped[str | None] = mapped_column(String(100))


class DataCenterReportVersion(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """发布版本快照；append-only，保证发布后继续编辑草稿不会污染领导已见口径。"""

    __tablename__ = "t_data_center_report_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "report_id", "version_no", name="uk_dc_report_version"),
        Index("ix_dc_report_ver_tenant_report", "tenant_id", "report_id", "version_no"),
    )

    report_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    metrics_json: Mapped[list | None] = mapped_column(JSON)
    trend_json: Mapped[dict | None] = mapped_column(JSON)
    as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    caliber_code: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_json: Mapped[dict | None] = mapped_column(JSON)
    source_json: Mapped[list | None] = mapped_column(JSON)
    quality_flags_json: Mapped[list | None] = mapped_column(JSON)
    published_by_id: Mapped[str | None] = mapped_column(String(100))
    published_by_name: Mapped[str | None] = mapped_column(String(100))
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
