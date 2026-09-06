"""Cross-plane authority corrections discovered after W0-W7 reverse audit."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.exceptions import AppException
from app.core.response import success
from app.modules.platform.routers import platform_router as _canonical

_routes = APIRouter(prefix="/platform", tags=["16·平台控制面·跨域Authority收口"])


@_routes.get("/tenants/{tenant_id}/features", summary="商业授权唯一真值投影")
def commercial_features_get(
    tenant_id: int,
    user=Depends(_canonical.require_platform_capability("commercial.view")),
):
    from app.services.commercial_entitlement_authority_service import features_projection
    return success(features_projection(int(tenant_id)))


@_routes.get("/tenants/{tenant_id}/brand", summary="学校品牌唯一真值只读投影")
def canonical_brand_get(
    tenant_id: int,
    user=Depends(_canonical.require_platform_capability("tenant.view")),
):
    from app.services.tenant_brand_authority_service import brand_projection
    return success(brand_projection(int(tenant_id)))


@_routes.put("/tenants/{tenant_id}/brand", summary="平台主管理不再维护第二套学校品牌真值")
def canonical_brand_put(
    tenant_id: int,
    body: dict = Body(...),
    user=Depends(_canonical.require_platform_capability("commercial.manage")),
):
    raise AppException(
        "BRAND_AUTHORITY_MOVED",
        "学校品牌唯一真值是 TenantBrandConfig；平台主管理端仅做只读投影，修改请由学校系统管理或受控协助执行",
        http_status=409,
        details={
            "tenantId": str(tenant_id),
            "authority": "TENANT_BRAND_CONFIG",
            "writeSurface": "/admin/system/config?tab=brand",
            "legacyPlatformBrandWriteDisabled": True,
            "requestedKeys": sorted(str(key) for key in (body or {}).keys()),
        },
    )


def _route_key(route) -> tuple[str, str]:
    methods = sorted(getattr(route, "methods", set()) or set())
    return (methods[0] if len(methods) == 1 else ",".join(methods), getattr(route, "path", ""))


def install_into_platform_router(target: APIRouter) -> None:
    from app.services.commercial_entitlement_authority_service import install_platform_service_adapter as install_entitlement
    from app.services.tenant_brand_authority_service import install_platform_service_adapter as install_brand

    install_entitlement()
    install_brand()

    replacement = {_route_key(route): route for route in _routes.routes}
    routes = []
    for route in target.routes:
        key = _route_key(route)
        routes.append(replacement.pop(key, route))
    routes.extend(replacement.values())
    target.routes[:] = routes
