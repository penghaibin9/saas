"""SYS-06 权限包、RoleTemplate 与学校自定义角色治理事实。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Index, Integer, String,
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

TEMPLATE_PLANE_TENANT = "TENANT"
TEMPLATE_PLANE_PLATFORM_PRODUCT = "PLATFORM_PRODUCT"
TEMPLATE_CATEGORY_SYSTEM_ROLE = "SYSTEM_ROLE"
TEMPLATE_DRAFT = "DRAFT"
TEMPLATE_PUBLISHED = "PUBLISHED"

WILDCARD_PENDING = "PENDING"
WILDCARD_PLANNED = "PLANNED"
WILDCARD_RETIRED = "RETIRED"


class PermissionBundle(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_permission_bundle"

    bundle_code: Mapped[str] = mapped_column(String(128), nullable=False)
    bundle_name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_domain: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default=BUNDLE_RISK_NORMAL)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("tenant_id", "bundle_code", name="uk_bundle_tenant_code"),
        Index("idx_bundle_owner_status", "owner_domain", "status"),
    )


class PermissionBundleItem(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_permission_bundle_item"

    bundle_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    permission_code: Mapped[str] = mapped_column(String(160), nullable=False)
    effect: Mapped[str] = mapped_column(String(8), nullable=False, default=EFFECT_ALLOW)

    __table_args__ = (
        UniqueConstraint("bundle_id", "permission_code", "effect", name="uk_bundle_permission"),
        Index("idx_bundle_item_permission", "permission_code"),
    )


class RoleTemplate(PKMixin, TenantMixin, CommonMixin, Base):
    """平台交付角色模板；版本发布事实不可原地覆盖。"""

    __tablename__ = "t_role_template"

    template_code: Mapped[str] = mapped_column(String(64), nullable=False)
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    template_plane: Mapped[str] = mapped_column(String(32), nullable=False, default=TEMPLATE_PLANE_TENANT)
    template_category: Mapped[str] = mapped_column(String(32), nullable=False, default=TEMPLATE_CATEGORY_SYSTEM_ROLE)
    publish_status: Mapped[str] = mapped_column(String(24), nullable=False, default=TEMPLATE_DRAFT)
    permission_digest: Mapped[str | None] = mapped_column(String(64))
    previous_template_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    change_reason: Mapped[str | None] = mapped_column(String(1000))
    source_commit_sha: Mapped[str | None] = mapped_column(String(64))
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_by: Mapped[int | None] = mapped_column(BigInteger)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bundle_codes_json: Mapped[dict | None] = mapped_column(JSON)
    permission_ceiling_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    wildcard_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("tenant_id", "template_code", "template_version", name="uk_role_template_version"),
        Index("idx_role_template_status", "tenant_id", "status"),
        Index("idx_role_template_publish", "tenant_id", "template_plane", "template_code", "publish_status"),
    )


class RoleTemplatePermission(PKMixin, TenantMixin, CommonMixin, Base):
    """RoleTemplate 的规范化权限关系；JSON 仅作兼容快照。"""

    __tablename__ = "t_role_template_permission"

    role_template_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    permission_code: Mapped[str] = mapped_column(String(160), nullable=False)
    effect: Mapped[str] = mapped_column(String(8), nullable=False, default=EFFECT_ALLOW)

    __table_args__ = (
        UniqueConstraint("role_template_id", "permission_code", "effect", name="uk_role_template_permission"),
        Index("idx_role_template_permission_code", "tenant_id", "permission_code", "effect"),
    )


class CustomRoleSource(PKMixin, TenantMixin, CommonMixin, Base):
    """CUSTOM 治理来源；role_id 是 t_role 的稳定 1:1 runtime identity。"""

    __tablename__ = "t_custom_role_source"

    # N-1 rolling compatibility: previous-release writers do not know role_id yet.
    # New Control Plane writes still populate it; a later contract migration may tighten NOT NULL.
    role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    source_template_code: Mapped[str] = mapped_column(String(64), nullable=False)
    source_template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    permission_codes_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    drift_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")

    __table_args__ = (
        UniqueConstraint("tenant_id", "role_code", name="uk_custom_role_source"),
        UniqueConstraint("tenant_id", "role_id", name="uk_custom_role_source_role"),
        Index("idx_custom_role_template", "tenant_id", "source_template_code"),
    )


class WildcardRetirement(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_wildcard_retirement"

    role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    wildcard_code: Mapped[str] = mapped_column(String(160), nullable=False)
    expanded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expanded_json: Mapped[dict | None] = mapped_column(JSON)
    replacement_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=WILDCARD_PENDING)
    note: Mapped[str | None] = mapped_column(String(1000))

    __table_args__ = (
        UniqueConstraint("tenant_id", "role_code", "wildcard_code", name="uk_wildcard_retirement"),
        Index("idx_wildcard_status", "tenant_id", "status"),
    )
