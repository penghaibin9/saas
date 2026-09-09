"""平台总控（P6）：通用配置存储 + 订单 + 公告。
t_platform_config 为控制面 KV（tenant_id=0 表示全局默认）；t_order 按冻结册 §4.1.5。
"""
from __future__ import annotations

from datetime import datetime
import sys as _sys

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin


class PlatformConfig(PKMixin, CommonMixin, Base):
    """t_platform_config 平台配置 KV：PACKAGE/FEATURES/RULES/WORKFLOWS/DICT/BRAND/SECURITY。"""
    __tablename__ = "t_platform_config"
    __table_args__ = (UniqueConstraint("tenant_id", "config_type", "config_key", name="uk_platform_cfg"),)

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, index=True,
                                           comment="0=全局默认；否则为租户覆盖")
    config_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    config_key: Mapped[str] = mapped_column(String(100), nullable=False, default="-")
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    remark: Mapped[str | None] = mapped_column(String(500))


class PlatformOrder(PKMixin, CommonMixin, Base):
    """t_order 订单（冻结册 §4.1.5，手工订单）。"""
    __tablename__ = "t_order"
    __table_args__ = (UniqueConstraint("order_no", name="uk_order_no"),)

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    order_no: Mapped[str] = mapped_column(String(100), nullable=False)
    order_type: Mapped[str] = mapped_column(String(50), nullable=False, default="NEW",
                                            comment="NEW/RENEW/UPGRADE/ADDON")
    package_code: Mapped[str | None] = mapped_column(String(50))
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="unpaid",
                                        comment="unpaid/paid/refunded/cancelled")
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


class PlatformNotice(PKMixin, CommonMixin, Base):
    """t_platform_notice 平台公告（全平台或指定租户；TODO 深化文档定稿后对齐）。"""
    __tablename__ = "t_platform_notice"

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, index=True,
                                           comment="0=全平台")
    notice_type: Mapped[str] = mapped_column(String(50), nullable=False, default="ANNOUNCEMENT",
                                             comment="ANNOUNCEMENT/EXPIRE_REMIND/MAINTENANCE/TRIAL_REMIND")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT",
                                        comment="DRAFT/PUBLISHED/OFFLINE")
    publish_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


# Register M1-M8 tables in Base.metadata while preserving the existing large
# app.models aggregator. Existing services import models from ``app.models``;
# expose the additions there without introducing a second model registry.
from app.models.commercial import (  # noqa: E402,F401
    CommercialInvoiceCase,
    CommercialOrderItem,
    CommercialRefundCase,
    CommercialSkuVersion,
    TenantCommercialProfile,
    TenantModuleCancellationPlan,
    TenantModuleOffboardingJob,
    TenantModuleOffboardingStep,
    TenantModuleState,
    TenantModuleSubscriptionSource,
)
from app.models.commercial_operations import (  # noqa: E402,F401
    CommercialAfterSalesLink,
    CommercialServiceCostRecord,
)

_models_package = _sys.modules.get("app.models")
if _models_package is not None:
    for _model_name in (
        "CommercialAfterSalesLink",
        "CommercialInvoiceCase",
        "CommercialOrderItem",
        "CommercialRefundCase",
        "CommercialServiceCostRecord",
        "CommercialSkuVersion",
        "TenantCommercialProfile",
        "TenantModuleCancellationPlan",
        "TenantModuleOffboardingJob",
        "TenantModuleOffboardingStep",
        "TenantModuleState",
        "TenantModuleSubscriptionSource",
    ):
        setattr(_models_package, _model_name, globals()[_model_name])
