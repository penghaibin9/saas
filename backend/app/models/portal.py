"""学生 PC 门户 · 租户级配置（studentPortal 开关/模块/功能/套餐/登录提示）。
与品牌表 TenantBrandConfig 分离；每租户一行，行级隔离 tenant_id 唯一。
config_json 存租户「覆盖配置」，最终门户配置由 student_portal_service 合并
（默认 < 套餐能力上限 < 租户覆盖 < 总开关）后下发，本表不存合并结果。"""
from __future__ import annotations

from sqlalchemy import JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class TenantPortalConfig(PKMixin, TenantMixin, CommonMixin, Base):
    """t_tenant_portal_config：学生 PC 门户租户配置（覆盖项，JSON）。"""
    __tablename__ = "t_tenant_portal_config"
    __table_args__ = (UniqueConstraint("tenant_id", name="uk_tenant_portal_config"),)

    config_json: Mapped[dict | None] = mapped_column(
        JSON, comment="studentPortal 覆盖配置：enabled/portalName/portalUrl/modules/features/requiredPackage/loginAccountTips")
