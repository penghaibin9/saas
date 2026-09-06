"""School system-management authority corrections shared with platform operations."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.permissions import require_permission
from app.core.response import success

_routes = APIRouter()


@_routes.get("/system/brand", summary="学校品牌唯一真值（TenantBrandConfig）")
def governed_system_brand_get(user=Depends(require_permission("systemAdmin.config.view"))):
    from app.services.tenant_brand_authority_service import brand_projection
    return success(brand_projection(int(current_tenant_id() or 0))["brand"])


@_routes.put("/system/brand", summary="学校品牌乐观锁写入唯一真值")
def governed_system_brand_put(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.config.manage")),
):
    from app.services.tenant_brand_authority_service import update_school_brand

    payload = dict(body or {})
    expected = payload.get("expectedVersion", payload.get("version"))
    return success(update_school_brand(
        int(current_tenant_id() or 0),
        brand=payload,
        expected_version=expected,
        reason=payload.get("reason") or "",
        user=user,
    ), message="品牌配置已保存并生效")


@_routes.post("/system/brand/reset", summary="恢复学校品牌默认值（行锁+版本校验兼容）")
def governed_system_brand_reset(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.config.manage")),
):
    from app.services.tenant_brand_authority_service import reset_school_brand

    payload = dict(body or {})
    return success(reset_school_brand(
        int(current_tenant_id() or 0),
        expected_version=payload.get("expectedVersion"),
        reason=payload.get("reason") or "",
        user=user,
    ), message="品牌配置已恢复默认值")


@_routes.put("/system/module-features", summary="旧整份模块开关写入口退役")
def governed_legacy_module_features_put(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.config.manage")),
):
    raise AppException(
        "CAPABILITY_AUTHORITY_MOVED",
        "模块启停已按能力键独立版本治理；请逐项调用 /system/capability-settings/{key} 并携带 expectedVersion",
        http_status=409,
        details={
            "writeSurface": "/api/v1/system/capability-settings/{key}",
            "legacyBulkWriteDisabled": True,
            "requestedKeys": sorted(str(key) for key in ((body or {}).get("features") or {}).keys()),
        },
    )


def _route_key(route) -> tuple[str, str]:
    methods = sorted(getattr(route, "methods", set()) or set())
    return (methods[0] if len(methods) == 1 else ",".join(methods), getattr(route, "path", ""))


def install_into_system_router(target: APIRouter) -> None:
    replacement = {_route_key(route): route for route in _routes.routes}
    routes = []
    for route in target.routes:
        key = _route_key(route)
        routes.append(replacement.pop(key, route))
    routes.extend(replacement.values())
    target.routes[:] = routes
