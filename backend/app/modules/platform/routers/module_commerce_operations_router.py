"""M8 commercial operations bridge.

Separate from both the frozen M1-M5 routes and the M8 finance 10-route contract.
This API reuses the existing customer-success ticket truth, observes SLA only from an
explicit policy, records actual service costs without currency conversion, and exposes
a governed PlatformConfig SLA editor. No default SLA hours are invented.
"""
from fastapi import APIRouter, Body, Depends, Header, Query

from app.core.response import success
from app.modules.platform.routers.platform_router import require_platform_capability

router = APIRouter(prefix="/platform", tags=["16·平台主管·商业售后治理"])


@router.get("/commercial/tenants/{tenant_id}/operations", summary="商业售后与持续治理总览")
def operations_overview(
    tenant_id: int,
    user=Depends(require_platform_capability("commercial.view")),
):
    from app.services import module_commerce_operations_service as operations
    return success(operations.operations_overview(int(tenant_id)))


@router.get("/commercial/tenants/{tenant_id}/after-sales", summary="退款后授权复核工单与SLA观察")
def after_sales(
    tenant_id: int,
    page: int = Query(1, ge=1, le=10000),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_platform_capability("commercial.view")),
):
    from app.services import module_commerce_operations_service as operations
    return success(operations.list_after_sales(int(tenant_id), page=page, page_size=pageSize))


@router.post("/commercial/tenants/{tenant_id}/refunds/{case_id}/after-sales-ticket", summary="显式创建退款后授权复核工单")
def create_after_sales_ticket(
    tenant_id: int,
    case_id: int,
    body: dict = Body(...),
    user=Depends(require_platform_capability("order.manage")),
):
    from app.services import module_commerce_operations_service as operations
    return success(
        operations.ensure_refund_after_sales_ticket(
            user, int(tenant_id), int(case_id),
            severity=str(body.get("severity") or ""), reason=str(body.get("reason") or ""),
        ),
        message="退款后授权复核已交给现有客户成功工单；没有自动修改模块授权",
    )


@router.get("/commercial/tenants/{tenant_id}/service-costs", summary="按币种查看实际服务成本")
def service_costs(
    tenant_id: int,
    page: int = Query(1, ge=1, le=10000),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_platform_capability("commercial.view")),
):
    from app.services import module_commerce_operations_service as operations
    return success(operations.list_service_costs(int(tenant_id), page=page, page_size=pageSize))


@router.post("/commercial/tenants/{tenant_id}/service-costs", summary="登记实际服务成本（不做币种换算）")
def record_service_cost(
    tenant_id: int,
    body: dict = Body(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user=Depends(require_platform_capability("order.manage")),
):
    from app.services import module_commerce_operations_service as operations
    return success(
        operations.record_service_cost(user, int(tenant_id), body, idempotency_key=idempotency_key),
        message="实际服务成本已登记；未进行币种换算或估算",
    )


@router.get("/commercial/tenants/{tenant_id}/sla-policy", summary="读取商业SLA有效政策与学校覆盖")
def sla_policy(
    tenant_id: int,
    user=Depends(require_platform_capability("commercial.view")),
):
    from app.services import module_commerce_sla_policy_service as policy
    return success(policy.policy_editor(int(tenant_id)))


@router.put("/commercial/tenants/{tenant_id}/sla-policy", summary="按expectedVersion保存学校商业SLA政策")
def update_sla_policy(
    tenant_id: int,
    body: dict = Body(...),
    user=Depends(require_platform_capability("commercial.manage")),
):
    from app.services import module_commerce_sla_policy_service as policy
    return success(
        policy.update_tenant_policy(user, int(tenant_id), body),
        message="学校商业SLA政策已保存；四级目标均来自本次明确输入，没有系统默认承诺",
    )


@router.post("/commercial/tenants/{tenant_id}/sla-policy/reset", summary="恢复平台SLA默认或未评估状态")
def reset_sla_policy(
    tenant_id: int,
    body: dict = Body(...),
    user=Depends(require_platform_capability("commercial.manage")),
):
    from app.services import module_commerce_sla_policy_service as policy
    return success(
        policy.reset_tenant_policy(
            user, int(tenant_id), expected_version=body.get("expectedVersion"),
            reason=str(body.get("reason") or ""),
        ),
        message="学校SLA覆盖已停用；后续回落到平台明确默认，若无默认则保持未评估",
    )


def install_into_platform_router(target: APIRouter) -> int:
    """Atomically install the isolated operations routes; collisions fail closed."""
    from fastapi.routing import APIRoute
    from app.core.commercial_surface_module_gate import iter_effective_route_contexts

    def keys(context):
        leaf = getattr(context, "route", context)
        fallback = getattr(context, "starlette_route", None) or leaf
        path = getattr(context, "path", None) or getattr(fallback, "path", "")
        methods = getattr(context, "methods", None) or getattr(fallback, "methods", None) or ()
        return {(str(method).upper(), path) for method in methods}

    existing = {}
    for context in iter_effective_route_contexts(target):
        route = getattr(context, "route", context)
        for key in keys(context):
            existing.setdefault(key, []).append(route)
    declared = set(); pending = []
    for route in router.routes:
        signatures = keys(route)
        if not isinstance(route, APIRoute) or not signatures or declared & signatures:
            raise RuntimeError("Invalid or duplicate module-commerce operations route declaration")
        declared.update(signatures)
        if all(len(existing.get(key, [])) == 1 and existing[key][0] is route for key in signatures):
            continue
        collisions = sorted(key for key in signatures if key in existing)
        if collisions:
            raise RuntimeError(f"Module-commerce operations route collision: {collisions}")
        pending.append(route)
    target.routes.extend(pending)
    return len(pending)
