"""SYS-11 配置治理：定义、分层覆盖与激活流水。

现状与增量
──────────
仓库里已经有这条继承链的雏形，本模块把它显式化，而不是另起炉灶：

====================  ==========================================================
链上的层              当前代码里的来源
====================  ==========================================================
PLATFORM_FLOOR        ``platform_defaults.SECURITY_BOUNDS``（保存时的合法区间）
PACKAGE_DEFAULT       ``platform_defaults.DEFAULT_PACKAGES`` / ``DEFAULT_SECURITY``
TENANT                ``t_sys_config``（学校已可编辑，被强制层真实读取）
ORG_UNIT / TERM       缺失，本模块补上
====================  ==========================================================

``t_sys_config`` 继续作为学校级配置的既有存储，不做破坏性搬迁；``t_config_override``
承载"分层 + 未来生效"的新能力，解析时按链合并。这样既补齐能力，又不会让已经生效的
登录锁定阈值等安全配置在升级瞬间改变行为。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Index, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (AuditTimeMixin, Base, CommonMixin, PKMixin,
                             TenantMixin)

# 覆盖层级，按优先级从低到高
SCOPE_TENANT = "TENANT"
SCOPE_ORG_UNIT = "ORG_UNIT"
SCOPE_TERM = "TERM"
OVERRIDE_SCOPES = (SCOPE_TENANT, SCOPE_ORG_UNIT, SCOPE_TERM)

# 解析结果里标记值来自哪一层
SOURCE_PLATFORM_FLOOR = "PLATFORM_FLOOR"
SOURCE_PACKAGE_DEFAULT = "PACKAGE_DEFAULT"
SOURCE_TENANT_LEGACY = "TENANT_LEGACY"  # 来自既有 t_sys_config
SOURCE_LAYERS = (
    SOURCE_PLATFORM_FLOOR,
    SOURCE_PACKAGE_DEFAULT,
    SOURCE_TENANT_LEGACY,
    SCOPE_TENANT,
    SCOPE_ORG_UNIT,
    SCOPE_TERM,
)

VALUE_TYPES = ("INT", "STRING", "BOOL", "JSON")

OVERRIDE_STATUS_PENDING = "PENDING"
OVERRIDE_STATUS_ACTIVE = "ACTIVE"
OVERRIDE_STATUS_EXPIRED = "EXPIRED"
OVERRIDE_STATUS_REVOKED = "REVOKED"


class ConfigDefinition(PKMixin, CommonMixin, Base):
    """配置项定义。平台级，不带 tenant_id——同一个配置键在所有学校含义必须一致。"""

    __tablename__ = "t_config_definition"

    config_key: Mapped[str] = mapped_column(String(160), nullable=False)
    domain_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="所属域：SECURITY/BRAND/ACADEMIC 等")
    config_name: Mapped[str | None] = mapped_column(String(200))
    value_type: Mapped[str] = mapped_column(String(24), nullable=False, default="STRING")
    validation_json: Mapped[dict | None] = mapped_column(JSON, comment="min/max/enum 等约束，保存前校验")
    default_json: Mapped[dict | None] = mapped_column(JSON, comment="套餐默认值")
    platform_floor_json: Mapped[dict | None] = mapped_column(JSON, comment="平台底线，学校不得突破")
    school_editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_code: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")
    consumer_json: Mapped[dict | None] = mapped_column(JSON, comment="谁在读这个配置；无消费者的配置不得声称即刻生效")
    cache_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="TENANT")
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="NORMAL")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("config_key", name="uk_config_definition_key"),
        Index("idx_config_definition_domain_status", "domain_code", "status"),
    )


class ConfigOverride(PKMixin, TenantMixin, CommonMixin, Base):
    """学校在某一层对某个配置的覆盖，支持未来生效与到期。"""

    __tablename__ = "t_config_override"

    config_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(24), nullable=False, default=SCOPE_TENANT)
    scope_id: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="ORG_UNIT/TERM 的目标 id")
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment='统一包一层 {"value": ...}')
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=OVERRIDE_STATUS_ACTIVE, index=True)
    reason: Mapped[str | None] = mapped_column(String(1000))

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "config_key", "scope_type", "scope_id", "effective_at", name="uk_config_override_scope"
        ),
        Index(
            "idx_config_override_effective",
            "tenant_id", "config_key", "status", "effective_at", "expires_at",
        ),
    )


class ConfigActivation(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """配置变更流水（append-only）。谁在什么时候把哪个配置从什么改成了什么。"""

    __tablename__ = "t_config_activation"

    config_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(24), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    before_json: Mapped[dict | None] = mapped_column(JSON)
    after_json: Mapped[dict | None] = mapped_column(JSON)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(String(1000))
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)

    __table_args__ = (Index("idx_config_activation_key_time", "tenant_id", "config_key", "created_at"),)
