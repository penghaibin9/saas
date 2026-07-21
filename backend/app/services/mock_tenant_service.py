"""
mock 租户 / 品牌配置服务
────────────────────────────────────────────────────────────
对应 UI 的 tenantBrandConfig（唯一来源），字段对齐 docs/05-数据接口权限与安全/api/01 §1.5、
DB 冻结册 t_tenant_brand_config。真实接库后此处改为查表 + file_id 转签名 URL。
"""
from __future__ import annotations

from app.core.context import get_tenant

_BRANDS = {
    "1000000000000000001": {
        "platformName": "示范职院学生成长平台",
        "platformSubtitle": "学生全生命周期管理",
        "browserTitle": "示范职院 · 学生成长平台",
        "logoLightUrl": "https://cdn.example.edu/demo/logo-light.png",
        "logoDarkUrl": "https://cdn.example.edu/demo/logo-dark.png",
        "faviconUrl": "https://cdn.example.edu/demo/favicon.ico",
        "loginBgUrl": "https://cdn.example.edu/demo/login-bg.jpg",
        "primaryColor": "#2563EB",
        "secondaryColor": "#0EA5E9",
        "defaultTheme": "academy_blue",
        "motto": "厚德 精技 笃行",
        "watermarkText": "示范职院内部系统",
    },
    "1000000000000000002": {
        "platformName": "华南商贸学生服务平台",
        "platformSubtitle": "一站式学生服务",
        "browserTitle": "华南商贸 · 学生服务",
        "logoLightUrl": "https://cdn.example.edu/hnsh/logo-light.png",
        "logoDarkUrl": "https://cdn.example.edu/hnsh/logo-dark.png",
        "faviconUrl": "https://cdn.example.edu/hnsh/favicon.ico",
        "loginBgUrl": "https://cdn.example.edu/hnsh/login-bg.jpg",
        "primaryColor": "#059669",
        "secondaryColor": "#10B981",
        "defaultTheme": "campus_green",
        "motto": "诚信 敬业 创新",
        "watermarkText": "华南商贸内部系统",
    },
}


def _db_brand_overlay(tenant_id: str) -> dict:
    """读 t_tenant_brand_config 覆盖层：学校侧编辑的品牌真实生效于顶栏/登录页。
    任何异常（未接库/无行/字段空）都返回空覆盖，回落 mock 基线，绝不阻断页面渲染。"""
    try:
        from app.db.session import db_enabled, get_sessionmaker
        if not db_enabled() or not str(tenant_id).isdigit():
            return {}
        from sqlalchemy import select
        from app.models import TenantBrandConfig
        db = get_sessionmaker()()
        try:
            row = db.scalars(select(TenantBrandConfig).where(
                TenantBrandConfig.tenant_id == int(tenant_id))).first()
            if row is None:
                return {}
            overlay = {}
            if row.platform_name: overlay["platformName"] = row.platform_name
            if row.platform_subtitle: overlay["platformSubtitle"] = row.platform_subtitle
            if row.primary_color: overlay["primaryColor"] = row.primary_color
            if row.secondary_color: overlay["secondaryColor"] = row.secondary_color
            if row.default_theme: overlay["defaultTheme"] = row.default_theme
            if row.motto: overlay["motto"] = row.motto
            if row.watermark_text: overlay["watermarkText"] = row.watermark_text
            extra = row.config_json if isinstance(row.config_json, dict) else {}
            for k in ("loginSlogan", "footerText", "watermarkDensity", "schoolShortName"):
                if extra.get(k) is not None:
                    overlay[k] = extra[k]
            return overlay
        finally:
            db.close()
    except Exception:
        return {}


def get_brand() -> dict:
    tenant = get_tenant() or {}
    tenant_id = tenant.get("tenantId", "1000000000000000001")
    base = _BRANDS.get(tenant_id, _BRANDS["1000000000000000001"])
    brand = {**base, **_db_brand_overlay(tenant_id)}  # DB 覆盖层优先（学校编辑真实生效）
    return {
        "tenantId": tenant_id,
        "tenantCode": tenant.get("tenantCode"),
        "tenantName": tenant.get("tenantName"),
        **brand,
        # ── 产品主名称统一（命名规范）：学校名走 schoolName，产品名不再返回旧名 ──
        "platformDisplayName": "高校学生全生命周期管理平台",
        "schoolName": tenant.get("tenantName") or "示范职业技术学院",
        "schoolLogo": brand.get("logoLightUrl"),
        "loginTitle": brand.get("platformName"),
        "topbarTitle": "高校学生全生命周期管理平台",
        "favicon": brand.get("faviconUrl"),
        "theme": brand.get("defaultTheme"),
        "enabledModules": ["student", "orientation", "campusService", "academic",
                            "internship", "graduation", "employment", "dataCenter",
                            "approval", "system"],
    }
