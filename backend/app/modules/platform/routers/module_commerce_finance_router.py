"""M8 commercial finance control-plane API.

This router is intentionally separate from the frozen M1-M5 24-route contract.
Receivable is derived from PlatformOrder; writes record refund/invoice control facts
or externally completed evidence only. No endpoint executes a refund, opens/voids an
invoice at a provider, changes PlatformOrder payment truth or mutates entitlement.
"""
from fastapi import APIRouter, Body, Depends, Header, Query

from app.core.exceptions import AppException
from app.core.response import success
from app.modules.platform.routers.platform_router import require_platform_capability

router = APIRouter(prefix="/platform", tags=["16·平台主管·商业财务"])


def _required_int(body: dict, key: str) -> int:
    try:
        value = body.get(key)
        if isinstance(value, bool):
            raise ValueError
        return int(value)
    except (TypeError, ValueError, OverflowError):
        raise AppException("VALIDATION_ERROR", f"{key} 必须是整数", http_status=422) from None


def _actor(user: dict):
    return user.get("userId") or "0"


@router.get("/commercial/tenants/{tenant_id}/finance-orders", summary="订单应收、退款与发票实时财务投影")
def finance_orders(
    tenant_id: int,
    page: int = Query(1, ge=1, le=10000),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_platform_capability("commercial.view")),
):
    from app.services import module_commerce_finance_service as finance
    return success(finance.list_finance_orders(int(tenant_id), page=page, page_size=pageSize))


@router.get("/commercial/tenants/{tenant_id}/refunds", summary="退款申请与外部结算台账")
def refunds(
    tenant_id: int,
    status: str = "",
    page: int = Query(1, ge=1, le=10000),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_platform_capability("commercial.view")),
):
    from app.services import module_commerce_finance_service as finance
    return success(finance.list_refunds(int(tenant_id), status=status, page=page, page_size=pageSize))


@router.post("/commercial/tenants/{tenant_id}/refunds", summary="发起人工退款申请（不执行退款）")
def request_refund(
    tenant_id: int,
    body: dict = Body(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user=Depends(require_platform_capability("order.manage")),
):
    from app.services import module_commerce_finance_service as finance
    payload = {**body, "tenantId": str(tenant_id)}
    return success(
        finance.request_refund(payload, idempotency_key=idempotency_key, actor_id=_actor(user)),
        message="退款申请已登记；系统未执行资金退款，也未改变模块授权",
    )


@router.post("/commercial/tenants/{tenant_id}/refunds/{case_id}/approve", summary="批准退款额度（不执行退款）")
def approve_refund(
    tenant_id: int, case_id: int, body: dict = Body(...),
    user=Depends(require_platform_capability("order.manage")),
):
    from app.services import module_commerce_finance_service as finance
    return success(
        finance.approve_refund(
            int(tenant_id), int(case_id), expected_version=_required_int(body, "expectedVersion"),
            note=str(body.get("note") or ""), actor_id=_actor(user),
        ),
        message="退款额度已批准；仍需在外部资金渠道实际退款后登记凭据",
    )


@router.post("/commercial/tenants/{tenant_id}/refunds/{case_id}/reject", summary="驳回退款申请")
def reject_refund(
    tenant_id: int, case_id: int, body: dict = Body(...),
    user=Depends(require_platform_capability("order.manage")),
):
    from app.services import module_commerce_finance_service as finance
    return success(finance.reject_refund(
        int(tenant_id), int(case_id), expected_version=_required_int(body, "expectedVersion"),
        reason=str(body.get("reason") or ""), actor_id=_actor(user),
    ), message="退款申请已驳回")


@router.post("/commercial/tenants/{tenant_id}/refunds/{case_id}/settle", summary="登记外部退款已完成凭据")
def settle_refund(
    tenant_id: int, case_id: int, body: dict = Body(...),
    user=Depends(require_platform_capability("order.manage")),
):
    from app.services import module_commerce_finance_service as finance
    return success(
        finance.settle_refund(
            int(tenant_id), int(case_id), expected_version=_required_int(body, "expectedVersion"),
            settlement_ref=str(body.get("settlementRef") or ""), actor_id=_actor(user),
        ),
        message="外部退款凭据已登记；订单支付真值和模块授权未被自动修改",
    )


@router.get("/commercial/tenants/{tenant_id}/invoices", summary="发票申请、开具与作废台账")
def invoices(
    tenant_id: int,
    status: str = "",
    page: int = Query(1, ge=1, le=10000),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_platform_capability("commercial.view")),
):
    from app.services import module_commerce_finance_service as finance
    return success(finance.list_invoices(int(tenant_id), status=status, page=page, page_size=pageSize))


@router.post("/commercial/tenants/{tenant_id}/invoices", summary="发起发票申请（不自动开票）")
def request_invoice(
    tenant_id: int,
    body: dict = Body(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user=Depends(require_platform_capability("order.manage")),
):
    from app.services import module_commerce_finance_service as finance
    payload = {**body, "tenantId": str(tenant_id)}
    return success(
        finance.request_invoice(payload, idempotency_key=idempotency_key, actor_id=_actor(user)),
        message="发票申请已登记；系统未调用税控或第三方开票服务",
    )


@router.post("/commercial/tenants/{tenant_id}/invoices/{invoice_case_id}/issue", summary="登记外部发票已开具")
def issue_invoice(
    tenant_id: int, invoice_case_id: int, body: dict = Body(...),
    user=Depends(require_platform_capability("order.manage")),
):
    from app.services import module_commerce_finance_service as finance
    return success(finance.issue_invoice(
        int(tenant_id), int(invoice_case_id), expected_version=_required_int(body, "expectedVersion"),
        external_invoice_ref=str(body.get("externalInvoiceRef") or ""),
        invoice_file_id=body.get("invoiceFileId"), actor_id=_actor(user),
    ), message="外部发票凭据已登记")


@router.post("/commercial/tenants/{tenant_id}/invoices/{invoice_case_id}/void", summary="登记外部发票已作废")
def void_invoice(
    tenant_id: int, invoice_case_id: int, body: dict = Body(...),
    user=Depends(require_platform_capability("order.manage")),
):
    from app.services import module_commerce_finance_service as finance
    return success(finance.void_invoice(
        int(tenant_id), int(invoice_case_id), expected_version=_required_int(body, "expectedVersion"),
        reason=str(body.get("reason") or ""), actor_id=_actor(user),
    ), message="发票作废事实已登记；系统未执行外部作废动作")


def install_into_platform_router(target: APIRouter) -> int:
    """Atomically install the isolated M8 routes without touching M1-M5 handlers."""
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

    declared = set()
    pending = []
    for route in router.routes:
        signatures = keys(route)
        if not isinstance(route, APIRoute) or not signatures or declared & signatures:
            raise RuntimeError("Invalid or duplicate module-commerce finance route declaration")
        declared.update(signatures)
        if all(len(existing.get(key, [])) == 1 and existing[key][0] is route for key in signatures):
            continue
        collisions = sorted(key for key in signatures if key in existing)
        if collisions:
            raise RuntimeError(f"Module-commerce finance route collision: {collisions}")
        pending.append(route)
    target.routes.extend(pending)
    return len(pending)
