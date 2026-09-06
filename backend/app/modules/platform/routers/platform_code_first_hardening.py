"""W1-W4 exact control-plane replacements layered over platform_router.

The S0 platform bundle is byte-frozen. This module mutates the already-composed
canonical APIRouter in place, replacing only exact (method, path) signatures.
That preserves ``app.api.v1.platform.router is platform_router.router`` while
allowing production authority contracts to evolve without touching the bundle.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.exceptions import AppException
from app.core.response import success
from app.modules.platform.routers import platform_bundle as _bundle
from app.modules.platform.routers import platform_router as _canonical

_routes = APIRouter(prefix="/platform", tags=["16·平台控制面·代码先行硬化"])


@_routes.get("/tenants/{tenant_id}/features", summary="商业授权投影（旧 override 只读对账）")
def governed_features_get(
    tenant_id: int,
    user=Depends(_canonical.require_platform_capability("commercial.view")),
):
    from app.services import platform_control_authority_service as authority

    return success(authority.features_projection(int(tenant_id)))


@_routes.put("/tenants/{tenant_id}/features", summary="拒绝通用 FEATURES 覆盖写入")
def governed_features_put(
    tenant_id: int,
    body: dict = Body(...),
    user=Depends(_canonical.require_platform_capability("commercial.manage")),
):
    raise AppException(
        "COMMERCIAL_AUTHORITY_REQUIRED",
        "商业授权不能直接写 FEATURES；正常授权必须由已支付订单生效，历史 override 仅供只读对账",
        http_status=409,
        details={
            "tenantId": str(tenant_id),
            "normalAuthority": "PAID_ORDER",
            "legacyWriteDisabled": True,
            "requestedKeys": sorted(str(key) for key in (body or {}).keys()),
        },
    )


@_routes.get("/tenants/{tenant_id}/workflows", summary="流程定义权威投影（旧 JSON 只读漂移证据）")
def governed_workflows_get(
    tenant_id: int,
    user=Depends(_bundle.require_platform_super_admin),
):
    from app.services import platform_control_authority_service as authority

    return success(authority.workflow_projection(int(tenant_id)))


@_routes.put("/tenants/{tenant_id}/workflows/{workflow_code}", summary="拒绝旧 WORKFLOWS JSON 写入")
def governed_workflow_put(
    tenant_id: int,
    workflow_code: str,
    body: dict = Body(...),
    user=Depends(_bundle.require_platform_super_admin),
):
    raise AppException(
        "WORKFLOW_AUTHORITY_MOVED",
        "审批流运行真值已统一到 WorkflowDefinition；平台主管旧 WORKFLOWS JSON 写入口已停止",
        http_status=409,
        details={
            "tenantId": str(tenant_id),
            "workflowCode": str(workflow_code),
            "authority": "WORKFLOW_DEFINITION",
            "writeSurface": "/admin/system/workflow-governance",
            "legacyWriteDisabled": True,
            "requestedKeys": sorted(str(key) for key in (body or {}).keys()),
        },
    )


@_routes.post("/tenants/{tenant_id}/transitions/{action}", summary="租户生命周期权威变更（commit/cache 分离回执）")
def governed_tenant_transition(
    tenant_id: int,
    action: str,
    body: dict = Body(...),
    user=Depends(_canonical.require_platform_capability("commercial.manage")),
):
    from app.services.platform_transition_receipt_service import apply_transition_with_receipt

    normalized = str(action or "").strip().lower()
    payload = dict(body or {})
    if normalized in {"change-package", "quota"}:
        grant_type = str(payload.get("exceptionGrantType") or "").strip().upper()
        approval_ref = str(payload.get("approvalRef") or "").strip()
        if grant_type not in {"GIFT", "SPECIAL_APPROVAL"} or len(approval_ref) < 5:
            raise AppException(
                "COMMERCIAL_ORDER_REQUIRED",
                "套餐或商业额度不能通过普通租户变更旁路订单；特批必须提供 exceptionGrantType 与 approvalRef",
                http_status=409,
                details={"action": normalized, "normalAuthority": "PAID_ORDER"},
            )
    audit_actions = {
        "enable": "PLATFORM_TENANT_ENABLE",
        "disable": "PLATFORM_TENANT_DISABLE",
        "extend-trial": "PLATFORM_TENANT_EXTEND_TRIAL",
        "convert-to-paid": "PLATFORM_TENANT_CONVERT_PAID",
        "expire": "PLATFORM_TENANT_EXPIRE",
        "change-package": "PLATFORM_TENANT_CHANGE_PACKAGE",
        "quota": "PLATFORM_TENANT_QUOTA",
    }
    out = apply_transition_with_receipt(
        int(tenant_id),
        normalized,
        reason=payload.get("reason"),
        expected_version=_bundle._expected_version(payload, operation="租户变更"),
        payload=payload,
        audit_action=audit_actions.get(normalized),
    )
    return success(out)


@_routes.post("/tenants/{tenant_id}/auth-cache/recover", summary="仅恢复租户权限缓存，不重放业务变更")
def governed_tenant_auth_cache_recover(
    tenant_id: int,
    user=Depends(_canonical.require_platform_capability("operations.manage")),
):
    from app.services.platform_transition_receipt_service import recover_tenant_auth_cache

    return success(recover_tenant_auth_cache(int(tenant_id)))


def _route_key(route) -> tuple[str, str]:
    methods = sorted(getattr(route, "methods", set()) or set())
    return (methods[0] if len(methods) == 1 else ",".join(methods), getattr(route, "path", ""))


def install_into_platform_router(target: APIRouter) -> None:
    """Replace exact signatures in-place; safe to call repeatedly."""
    replacement = {_route_key(route): route for route in _routes.routes}
    routes = []
    for route in target.routes:
        key = _route_key(route)
        routes.append(replacement.pop(key, route))
    routes.extend(replacement.values())
    target.routes[:] = routes
