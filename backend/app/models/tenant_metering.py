"""PLAT-13 租户用量、容量、成本与公平使用。

t_tenant_usage_snapshot 是新的每日时序数据，不是重复实现——SYS-19 的
usage_snapshot()/anomaly_snapshot() 只给"此刻"的实时快照、不存历史，这里
按天落一条记录才能画出用量趋势；容量口径本身仍是 SYS-19 的权威（这里只
读取它的实时聚合值写进当天快照，不重新计算）。t_tenant_fair_use_limit /
t_tenant_fair_use_violation 是"公平使用"要保护共享核心服务不被单租户
拖垮的配额与违规记录，同样不存在于任何既有表。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class TenantUsageSnapshot(PKMixin, TenantMixin, CommonMixin, Base):
    """t_tenant_usage_snapshot 每日用量快照（每租户每天一条）。"""
    __tablename__ = "t_tenant_usage_snapshot"
    __table_args__ = (UniqueConstraint("tenant_id", "snapshot_date", name="uk_tenant_usage_snapshot_day"),)

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    audit_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_upload_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    storage_total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    student_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TenantFairUseLimit(PKMixin, TenantMixin, CommonMixin, Base):
    """t_tenant_fair_use_limit 每租户可覆盖默认值的公平使用配额。"""
    __tablename__ = "t_tenant_fair_use_limit"
    __table_args__ = (UniqueConstraint("tenant_id", "resource_code", name="uk_tenant_fair_use_limit_resource"),)

    resource_code: Mapped[str] = mapped_column(String(40), nullable=False,
                                               comment="AUDIT_EVENTS_PER_DAY/FILE_UPLOAD_BYTES_PER_DAY")
    daily_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE",
                                        comment="ACTIVE/SUSPENDED（学校核心业务保护性限流已触发）")


class TenantFairUseViolation(PKMixin, TenantMixin, CommonMixin, Base):
    """t_tenant_fair_use_violation 超配额记录（append-only 性质，沿用统一字段口径）。"""
    __tablename__ = "t_tenant_fair_use_violation"

    resource_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    violation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    actual_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    limit_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action_taken: Mapped[str] = mapped_column(String(20), nullable=False, default="LOGGED",
                                              comment="LOGGED/THROTTLED/SUSPENDED")
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
