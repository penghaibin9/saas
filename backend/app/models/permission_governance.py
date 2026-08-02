"""SYS-06 权限包、交付角色模板与学校自定义角色来源。

必须先讲清楚的事实
──────────────────
当前**真实鉴权来源是代码常量** ``app.core.permissions.ROLE_PERMISSIONS``（一个
``dict[str, set[str]]``），不是 ``t_role`` / ``t_role_permission``。里面还存在
``SCHOOL_ADMIN: {"*"}`` 这样的全权通配和大量 ``module.*``。

因此本模块**不接管鉴权**，只建治理层：把散落的权限码组织成稳定权限包、把当前代码里的
角色固化为交付模板（DELIVERED，只读）、让学校自定义角色必须从模板复制且不得超出模板
上限，并把通配权限登记进退役队列。鉴权切换到数据库是后续独立步骤，需要双读对账，
在这里一次性切换风险不可控（全系统登录与权限会同时受影响）。
"""
from __future__ import annotations

from sqlalchemy import (JSON, BigInteger, Boolean, Index, Integer, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

BUNDLE_RISK_NORMAL = "NORMAL"
BUNDLE_RISK_HIGH = "HIGH"
BUNDLE_RISK_CRITICAL = "CRITICAL"

EFFECT_ALLOW = "ALLOW"
EFFECT_DENY = "DENY"

ROLE_SOURCE_DELIVERED = "DELIVERED"
ROLE_SOURCE_CUSTOM = "CUSTOM"

# 通配退役状态
WILDCARD_PENDING = "PENDING"      # 已登记，仍在使用
WILDCARD_PLANNED = "PLANNED"      # 已排定替换方案
WILDCARD_RETIRED = "RETIRED"      # 已替换为显式清单


class PermissionBundle(PKMixin, TenantMixin, CommonMixin, Base):
    """权限包：一组稳定的原子权限。``tenant_id=0`` 表示平台交付包，各校共享。"""

    __tablename__ = "t_permission_bundle"

    bundle_code: Mapped[str] = mapped_column(String(128), nullable=False)
    bundle_name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_domain: Mapped[str] = mapped_column(String(64), nullable=False, comment="归属域：SYSTEM/ACADEMIC/AFFAIRS 等")
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default=BUNDLE_RISK_NORMAL)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="平台交付包，学校只读")
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("tenant_id", "bundle_code", name="uk_bundle_tenant_code"),
        Index("idx_bundle_owner_status", "owner_domain", "status"),
    )


class PermissionBundleItem(PKMixin, TenantMixin, CommonMixin, Base):
    """包内的一条原子权限。DENY 项优先于任何 ALLOW。"""

    __tablename__ = "t_permission_bundle_item"

    bundle_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    permission_code: Mapped[str] = mapped_column(String(160), nullable=False)
    effect: Mapped[str] = mapped_column(String(8), nullable=False, default=EFFECT_ALLOW)

    __table_args__ = (
        UniqueConstraint("bundle_id", "permission_code", "effect", name="uk_bundle_permission"),
        Index("idx_bundle_item_permission", "permission_code"),
    )


class RoleTemplate(PKMixin, TenantMixin, CommonMixin, Base):
    """交付角色模板。从当前 ROLE_PERMISSIONS 固化而来，学校不得直接修改。"""

    __tablename__ = "t_role_template"

    template_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="对应 ROLE_PERMISSIONS 的角色码")
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bundle_codes_json: Mapped[dict | None] = mapped_column(JSON, comment="模板包含的权限包")
    permission_ceiling_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="模板权限上限的展开快照；学校角色必须是它的子集"
    )
    wildcard_json: Mapped[dict | None] = mapped_column(JSON, comment="该模板当前仍持有的通配权限")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("tenant_id", "template_code", "template_version", name="uk_role_template_version"),
        Index("idx_role_template_status", "tenant_id", "status"),
    )


class CustomRoleSource(PKMixin, TenantMixin, CommonMixin, Base):
    """学校自定义角色的来源登记：它是从哪个模板的哪个版本复制出来的。"""

    __tablename__ = "t_custom_role_source"

    role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    source_template_code: Mapped[str] = mapped_column(String(64), nullable=False)
    source_template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    permission_codes_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="裁剪后的权限清单")
    drift_json: Mapped[dict | None] = mapped_column(JSON, comment="与模板当前版本的差异快照")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")

    __table_args__ = (
        UniqueConstraint("tenant_id", "role_code", name="uk_custom_role_source"),
        Index("idx_custom_role_template", "tenant_id", "source_template_code"),
    )


class WildcardRetirement(PKMixin, TenantMixin, CommonMixin, Base):
    """通配权限退役队列：哪个角色持有什么通配、展开后覆盖多少权限码、打算怎么替换。

    ``*`` 和 ``module.*`` 不能一夜之间删掉——真删了会让学校管理员立刻失去全部权限。
    这张表让退役过程可见、可排期、可验证。
    """

    __tablename__ = "t_wildcard_retirement"

    role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    wildcard_code: Mapped[str] = mapped_column(String(160), nullable=False, comment='如 "*" 或 "systemAdmin.*"')
    expanded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="展开后覆盖的权限码数")
    expanded_json: Mapped[dict | None] = mapped_column(JSON, comment="展开清单快照，供替换时比对")
    replacement_json: Mapped[dict | None] = mapped_column(JSON, comment="拟替换为的显式权限清单")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=WILDCARD_PENDING)
    note: Mapped[str | None] = mapped_column(String(1000))

    __table_args__ = (
        UniqueConstraint("tenant_id", "role_code", "wildcard_code", name="uk_wildcard_retirement"),
        Index("idx_wildcard_status", "tenant_id", "status"),
    )
