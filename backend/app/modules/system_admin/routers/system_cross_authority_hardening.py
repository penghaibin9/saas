"""School system-management authority corrections shared with platform operations."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.permissions import require_any_permission, require_permission
from app.core.response import success

_routes = APIRouter()


def _capability_write_moved(*args, **kwargs):
    raise AppException(
        "CAPABILITY_AUTHORITY_MOVED",
        "模块启停已按能力键独立版本治理；请逐项调用 /system/capability-settings/{key} 并携带 expectedVersion",
        http_status=409,
        details={
            "writeSurface": "/api/v1/system/capability-settings/{key}",
            "legacyBulkWriteDisabled": True,
        },
    )


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


@_routes.post("/system/brand/reset", summary="恢复学校品牌默认值（强制 expectedVersion）")
def governed_system_brand_reset(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.config.manage")),
):
    from app.services.tenant_brand_authority_service import reset_school_brand

    payload = dict(body or {})
    return success(reset_school_brand(
        int(current_tenant_id() or 0),
        expected_version=payload.get("expectedVersion", payload.get("version")),
        reason=payload.get("reason") or "",
        user=user,
    ), message="品牌配置已恢复默认值")


@_routes.put("/system/module-features", summary="旧整份模块开关写入口退役")
def governed_legacy_module_features_put(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.config.manage")),
):
    _capability_write_moved(body, user=user)


# ── System mutation receipt: durable fact != cache refresh ───────────────────
@_routes.put("/system/users/{user_id}/status", summary="账号状态变更（提交/缓存结果分离）")
def governed_user_status(
    user_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.user.manage")),
):
    from app.services.system_mutation_receipt_service import set_user_status

    payload = dict(body or {})
    out = set_user_status(
        user_id,
        action=payload.get("action") or "",
        reason=payload.get("reason") or "",
        expected_version=payload.get("expectedVersion"),
        user=user,
    )
    action = str(payload.get("action") or "").upper()
    message = "账号已停用" if action == "DISABLE" else ("账号已解锁" if action == "UNLOCK" else "账号已启用")
    return success(out, message=message)


@_routes.post("/system/users/{user_id}/reset-password", summary="重置密码（一次性凭据不被缓存失败吞掉）")
def governed_reset_password(
    user_id: int,
    body: dict | None = Body(default=None),
    user=Depends(require_permission("systemAdmin.user.manage")),
):
    from app.services.system_mutation_receipt_service import reset_user_password

    payload = body if isinstance(body, dict) else {}
    return success(reset_user_password(
        user_id,
        expected_version=payload.get("expectedVersion"),
        reason=payload.get("reason") or "管理员重置密码",
        user=user,
    ), message="密码已重置")


@_routes.put("/system/user-batch-status", summary="批量账号状态变更（逐项缓存结果）")
def governed_batch_user_status(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.user.manage")),
):
    from app.services.system_mutation_receipt_service import batch_set_user_status

    out = batch_set_user_status(dict(body or {}), user=user)
    return success(out, message=f"已处理 {out['succeeded']} 个账号")


@_routes.put("/system/roles/{role_id}/status", summary="角色状态变更（提交/缓存结果分离）")
def governed_role_status(
    role_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.role.config")),
):
    from app.services.system_mutation_receipt_service import set_role_status

    payload = dict(body or {})
    out = set_role_status(
        role_id,
        action=payload.get("action") or "",
        reason=payload.get("reason") or "",
        expected_version=payload.get("expectedVersion"),
        user=user,
    )
    return success(out, message="角色已停用" if str(payload.get("action") or "").upper() == "DISABLE" else "角色已启用")


@_routes.post("/system/users/{user_id}/auth-cache/recover", summary="仅恢复指定账号权限缓存")
def governed_user_cache_recovery(
    user_id: int,
    user=Depends(require_permission("systemAdmin.user.manage")),
):
    from app.services.system_mutation_receipt_service import recover_subject_cache

    return success(recover_subject_cache(user_id), message="账号权限缓存恢复已执行")


@_routes.post("/system/auth-cache/recover", summary="仅恢复当前学校权限缓存")
def governed_tenant_cache_recovery(
    user=Depends(require_any_permission("systemAdmin.user.manage", "systemAdmin.role.config")),
):
    from app.services.system_mutation_receipt_service import recover_tenant_auth_cache

    return success(recover_tenant_auth_cache(), message="学校权限缓存恢复已执行")


def _route_key(route) -> tuple[str, str]:
    methods = sorted(getattr(route, "methods", set()) or set())
    return (methods[0] if len(methods) == 1 else ",".join(methods), getattr(route, "path", ""))


def install_into_system_router(target: APIRouter) -> None:
    # Frozen bundle functions may be called directly by internal compatibility
    # code/tests. Retire the service writer as well as the HTTP route so there is
    # one write Authority at every layer.
    from app.services import system_governance_service as governance

    governance.save_module_features = _capability_write_moved

    replacement = {_route_key(route): route for route in _routes.routes}
    routes = []
    for route in target.routes:
        key = _route_key(route)
        routes.append(replacement.pop(key, route))
    routes.extend(replacement.values())
    target.routes[:] = routes
