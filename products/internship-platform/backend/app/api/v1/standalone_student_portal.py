"""Minimal student-PC shell endpoints owned by internship standalone.

Do not import the parent SaaS mobile aggregation router here. The standalone
student PC needs only its own brand/module projection; internship business truth
continues to come from /portal/internship/* and shared internship services.
"""
from __future__ import annotations

from sqlalchemy import select

from fastapi import APIRouter, Depends

from app.config import settings
from app.core.exceptions import unauthorized
from app.core.response import success
from app.core.security import require_mobile_student
from app.db.session import get_sessionmaker
from app.models import Tenant
from app.models.tenant import TenantBrandConfig

router = APIRouter(prefix="/mobile/me", tags=["Standalone student PC shell"])


@router.get("/portal-config", summary="Standalone 学生 PC 岗位实习门户配置")
def portal_config(user=Depends(require_mobile_student)):
    raw_tenant = str((user or {}).get("tenantId") or (user or {}).get("tenant_id") or "")
    if not raw_tenant.isdigit() or int(raw_tenant) <= 0:
        raise unauthorized("学生令牌缺少学校上下文")
    tenant_id = int(raw_tenant)

    db = get_sessionmaker()()
    try:
        tenant = db.scalar(select(Tenant).where(
            Tenant.id == tenant_id,
            Tenant.is_deleted.is_(False),
            Tenant.status == "ACTIVE",
        ))
        if not tenant:
            raise unauthorized("学校不存在或已停用")
        brand = db.scalar(select(TenantBrandConfig).where(
            TenantBrandConfig.tenant_id == tenant_id,
            TenantBrandConfig.is_deleted.is_(False),
        ))
        return success({
            "enabled": True,
            "modules": {"internship": True},
            "features": {},
            "brand": {
                "schoolName": tenant.school_name,
                "platformName": (
                    getattr(brand, "platform_name", None)
                    or settings.APP_NAME
                    or "跃科岗位实习管理平台"
                ),
                "platformSubtitle": getattr(brand, "platform_subtitle", None) or "",
                "primaryColor": getattr(brand, "primary_color", None) or "#2f6bff",
            },
        })
    finally:
        db.close()
