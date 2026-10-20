"""租户与品牌（冻结册 §4.1 完整 DDL）。t_tenant 为控制面表：无 tenant_id。"""
from __future__ import annotations

from sqlalchemy import JSON, BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin


class Tenant(PKMixin, CommonMixin, Base):
    """t_tenant 租户（学校）——控制面，无 tenant_id 列（自身即租户维度）。"""
    __tablename__ = "t_tenant"
    __table_args__ = (UniqueConstraint("tenant_code", name="uk_tenant_code"),)

    tenant_code: Mapped[str] = mapped_column(String(50), nullable=False, comment="租户编码（学校唯一标识）")
    school_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="学校全称")
    short_name: Mapped[str | None] = mapped_column(String(100), comment="学校简称")
    region_code: Mapped[str | None] = mapped_column(String(50), comment="省市区编码")
    deploy_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="SAAS", comment="SAAS/PRIVATE")
    db_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="SHARED", comment="一期恒 SHARED（行级隔离）")
    db_name: Mapped[str | None] = mapped_column(String(100), comment="仅后期私有化预留，一期 NULL")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE",
                                        comment="PROVISIONING/ACTIVE/SUSPENDED/ARCHIVED")
    contact_name: Mapped[str | None] = mapped_column(String(100))
    contact_phone_encrypted: Mapped[str | None] = mapped_column(String(500), comment="敏感：联系人电话密文（§17.2）")


class TenantBrandConfig(PKMixin, CommonMixin, Base):
    """t_tenant_brand_config 学校品牌配置——UI tenantBrandConfig 唯一来源（§4.1.2）。"""
    __tablename__ = "t_tenant_brand_config"
    __table_args__ = (UniqueConstraint("tenant_id", name="uk_tenant_brand"),)

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="租户ID")
    platform_name: Mapped[str | None] = mapped_column(String(200), comment="平台名称（顶栏主名称）")
    platform_subtitle: Mapped[str | None] = mapped_column(String(200))
    browser_title: Mapped[str | None] = mapped_column(String(200))
    logo_light_file_id: Mapped[int | None] = mapped_column(BigInteger)
    logo_dark_file_id: Mapped[int | None] = mapped_column(BigInteger)
    favicon_file_id: Mapped[int | None] = mapped_column(BigInteger)
    badge_file_id: Mapped[int | None] = mapped_column(BigInteger, comment="校徽")
    login_bg_file_id: Mapped[int | None] = mapped_column(BigInteger)
    campus_line_file_id: Mapped[int | None] = mapped_column(BigInteger, comment="校园线稿/主楼")
    primary_color: Mapped[str | None] = mapped_column(String(20), comment="品牌主色，如 #2563EB")
    secondary_color: Mapped[str | None] = mapped_column(String(20))
    default_theme: Mapped[str | None] = mapped_column(String(50), comment="academy_blue/business_blue/eye_green/mono/gray")
    motto: Mapped[str | None] = mapped_column(String(200), comment="校训")
    watermark_text: Mapped[str | None] = mapped_column(String(200), comment="页面水印文案")
    config_json: Mapped[dict | None] = mapped_column(JSON, comment="其余可扩展品牌项（PG 落地为 JSONB）")
