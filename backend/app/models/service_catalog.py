"""PLAT-08 服务目录、依赖与租户影响地图。

平台级实体，不按学校隔离——服务目录、依赖图、runbook 是平台自己维护的
运行知识，不是租户业务数据。t_service_tenant_usage 记录"哪个租户用了哪个
服务"，用于故障影响面计算，同样由平台侧写入/查询，不经过 _tid() 租户上下文。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin


class PlatformService(PKMixin, CommonMixin, Base):
    """t_platform_service 服务目录条目。"""
    __tablename__ = "t_platform_service"
    __table_args__ = (UniqueConstraint("service_code", name="uk_platform_service_code"),)

    service_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    service_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tier: Mapped[str] = mapped_column(String(10), nullable=False, default="P2",
                                      comment="P0/P1/P2/P3")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE",
                                        comment="ACTIVE/DEGRADED/DEPRECATED")
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger)
    owner_name: Mapped[str | None] = mapped_column(String(100))
    responders_json: Mapped[list | None] = mapped_column(JSON, comment="值班responders列表")
    approvers_json: Mapped[list | None] = mapped_column(JSON, comment="变更审批人列表")
    runbook_url: Mapped[str | None] = mapped_column(String(500))
    monitoring_url: Mapped[str | None] = mapped_column(String(500))
    slo_target: Mapped[str | None] = mapped_column(String(50), comment="如 99.9%")
    description: Mapped[str | None] = mapped_column(String(1000))


class ServiceDependency(PKMixin, CommonMixin, Base):
    """t_service_dependency 服务依赖边：service_code 依赖 depends_on_service_code。"""
    __tablename__ = "t_service_dependency"
    __table_args__ = (
        UniqueConstraint("service_code", "depends_on_service_code", name="uk_service_dependency_edge"),
    )

    service_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    depends_on_service_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dependency_type: Mapped[str] = mapped_column(String(10), nullable=False, default="HARD",
                                                 comment="HARD/SOFT")


class ServiceTenantUsage(PKMixin, CommonMixin, Base):
    """t_service_tenant_usage 租户实际使用某服务的登记（故障影响面计算的数据源）。"""
    __tablename__ = "t_service_tenant_usage"
    __table_args__ = (
        UniqueConstraint("service_code", "tenant_id", name="uk_service_tenant_usage"),
    )

    service_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    usage_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE",
                                              comment="ACTIVE/INACTIVE")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
