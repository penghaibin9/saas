"""SYS-13 学校能力启用设置（结构化，取代整份 MODULE_FEATURES JSON 覆盖）。

为什么要单独一张表
──────────────────
原实现把全校模块开关塞在 ``t_system_json_doc`` 的一份 JSON 里（doc_key=MODULE_FEATURES），
版本号是**整份文档**级别的：两个管理员各改一个模块，后提交的那个必然撞 DATA_CONFLICT，
或者在没带 expectedVersion 时把对方的改动整份覆盖掉。SYS-13 要求「学校写使用
PUT /system/capability-settings/{key} 并带 expectedVersion」「不再整份 MODULE_FEATURES
JSON 覆盖」，所以按 (tenant_id, capability_key) 一行一锁。

capability_key 取 ``shared/contracts/module-manifest.json`` 的 moduleKey（schoolVisible
且非 platformOnly 的那些），依赖关系直接复用 manifest 的 dependencies，不另立一套。

entitled（平台是否售出）不落这张表：它的权威源是平台套餐/订单
（``platform_service.feature_enabled``）。学校只能写 enabled，写不了 entitled——
两者合成一个字段正是本卡明令禁止的。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, DateTime, Index, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class TenantCapabilitySetting(PKMixin, TenantMixin, CommonMixin, Base):
    """一行 = 一个学校对一个能力的启停决定。没有行 = 学校从未表态（按默认启用推导）。"""

    __tablename__ = "t_tenant_capability_setting"

    capability_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="module-manifest.moduleKey")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason: Mapped[str | None] = mapped_column(String(500), comment="最近一次启停原因，写入审计")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, comment="学校自定义启用期限，到期视同停用")
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_changed_by: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        UniqueConstraint("tenant_id", "capability_key", name="uk_tenant_capability"),
        Index("idx_tenant_capability_enabled", "tenant_id", "enabled"),
    )
