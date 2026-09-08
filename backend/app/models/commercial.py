"""Module-commerce persistence for M1/M2.

These tables extend the existing ``t_order`` payment truth. They do not replace
IAM, tenant capability settings, or the commercial entitlement read facade.
Existing tenants remain on the legacy reader until an explicit cutover profile
is created; new itemized contracts can use MODULE_V2 without rewriting legacy
orders.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class CommercialSkuVersion(PKMixin, CommonMixin, Base):
    __tablename__ = "t_commercial_sku_version"
    __table_args__ = (
        UniqueConstraint("sku_code", "sku_revision", name="uk_commercial_sku_version"),
        UniqueConstraint("content_hash", name="uk_commercial_sku_content_hash"),
    )

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, index=True,
                                           comment="0=platform catalogue")
    sku_code: Mapped[str] = mapped_column(String(64), nullable=False)
    sku_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), nullable=False)
    module_key: Mapped[str | None] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    lifecycle_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    publish_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PUBLISHED")
    retired_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


class CommercialOrderItem(PKMixin, CommonMixin, Base):
    __tablename__ = "t_commercial_order_item"
    __table_args__ = (
        UniqueConstraint("order_id", "line_no", name="uk_commercial_order_item_line"),
        Index("ix_commercial_order_item_tenant_module_window", "tenant_id", "module_key", "service_start_at", "service_end_at"),
    )

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_order.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sku_code: Mapped[str | None] = mapped_column(String(64))
    sku_revision: Mapped[int | None] = mapped_column(BigInteger)
    sku_content_hash: Mapped[str | None] = mapped_column(String(64))
    module_key: Mapped[str | None] = mapped_column(String(64), index=True)
    module_generation: Mapped[int | None] = mapped_column(BigInteger)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str | None] = mapped_column(String(3))
    service_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    service_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    sku_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    feature_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    quota_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fulfillment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime)


class TenantCommercialProfile(PKMixin, CommonMixin, TenantMixin, Base):
    __tablename__ = "t_tenant_commercial_profile"
    __table_args__ = (UniqueConstraint("tenant_id", name="uk_tenant_commercial_profile"),)

    reader_version: Mapped[str] = mapped_column(String(20), nullable=False, default="LEGACY")
    migration_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_STARTED")
    shadow_digest: Mapped[str | None] = mapped_column(String(64))
    switched_at: Mapped[datetime | None] = mapped_column(DateTime)
    switch_reason: Mapped[str | None] = mapped_column(String(500))


class TenantModuleState(PKMixin, CommonMixin, TenantMixin, Base):
    __tablename__ = "t_tenant_module_state"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_key", name="uk_tenant_module_state"),
        Index("ix_tenant_module_state_data", "tenant_id", "data_state"),
    )

    module_key: Mapped[str] = mapped_column(String(64), nullable=False)
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    lifecycle_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    data_state: Mapped[str] = mapped_column(String(20), nullable=False, default="AVAILABLE")
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime)


class TenantModuleSubscriptionSource(PKMixin, CommonMixin, TenantMixin, Base):
    __tablename__ = "t_tenant_module_subscription_source"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_type", "source_ref", "module_key", name="uk_tenant_module_source"),
        Index("ix_tenant_module_source_window", "tenant_id", "module_key", "status", "starts_at", "ends_at"),
    )

    module_key: Mapped[str] = mapped_column(String(64), nullable=False)
    module_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    order_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("t_commercial_order_item.id"), index=True)
    feature_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    quota_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    approval_ref: Mapped[str | None] = mapped_column(String(100))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
