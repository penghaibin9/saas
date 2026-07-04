"""
mock 租户 / 品牌配置服务
────────────────────────────────────────────────────────────
对应 UI 的 tenantBrandConfig（唯一来源），字段对齐 docs/api/01 §1.5、
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


def get_brand() -> dict:
    tenant = get_tenant() or {}
    tenant_id = tenant.get("tenantId", "1000000000000000001")
    brand = _BRANDS.get(tenant_id, _BRANDS["1000000000000000001"])
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
