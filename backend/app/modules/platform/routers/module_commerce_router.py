"""M1-M5 module-commerce control-plane API.

Runtime authority remains the canonical commercial entitlement facade. M3-M5
commands expose module portfolio, reversible stop/exit and verified export
acceptance. No endpoint in this router performs physical purge.
"""
from fastapi import APIRouter, Body, Depends, Header

from app.core.exceptions import AppException
from app.core.response import success
from app.modules.platform.routers.platform_router import require_platform_capability

router = APIRouter(prefix="/platform", tags=["16·平台主管·模块商业化"])


def _required_int(body: dict, key: str) -> int:
    try:
        value = body.get(key)
        if isinstance(value, bool): raise ValueError
        return int(value)
    except (TypeError, ValueError, OverflowError):
        raise AppException("VALIDATION_ERROR", f"{key} 必须是整数", http_status=422) from None


@router.post("/commercial/skus", summary="发布不可变模块SKU")
def publish_sku(body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import commercial_catalog_service as catalogue
    payload = body.get("sku") if isinstance(body.get("sku"), dict) else body
    return success(catalogue.publish_sku(payload, reason=str(body.get("reason") or ""), actor_id=user.get("userId")), message="商品版本已发布；尚未给任何学校授权")


@router.post("/commercial/orders", summary="创建模块分项订单")
def create_order(body: dict = Body(...), idempotency_key: str = Header(..., alias="Idempotency-Key"), user=Depends(require_platform_capability("order.manage"))):
    from app.services import commercial_order_item_service as orders
    return success(orders.create_itemized_order(body, idempotency_key=idempotency_key, actor_id=user.get("userId") or "0"), message="分项订单已创建（未支付、未授权）")


@router.get("/commercial/tenants/{tenant_id}/projection", summary="查看商业授权唯一投影")
def projection(tenant_id: int, user=Depends(require_platform_capability("commercial.view"))):
    from app.services import commercial_entitlement_authority_service as commercial
    return success(commercial.commercial_state(int(tenant_id)))


@router.get("/commercial/tenants/{tenant_id}/modules", summary="学校360模块订阅、用量与退出状态")
def module_portfolio(tenant_id: int, user=Depends(require_platform_capability("commercial.view"))):
    from app.services import module_commerce_lifecycle_service as lifecycle
    return success(lifecycle.tenant_module_portfolio(int(tenant_id)))


@router.get("/commercial/tenants/{tenant_id}/shadow", summary="查看LEGACY与MODULE_V2影子差异")
def shadow(tenant_id: int, user=Depends(require_platform_capability("commercial.view"))):
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import module_subscription_service as subscriptions
    legacy = commercial.legacy_commercial_state_for_reconciliation(int(tenant_id)); out = subscriptions.shadow_reconcile_tenant(int(tenant_id), legacy_features=legacy["features"])
    out["legacyAuthoritySource"] = legacy.get("authoritySource"); out["migrationClassification"] = subscriptions.classify_legacy_authority(legacy); return success(out)


@router.post("/commercial/tenants/{tenant_id}/modules/{module_key}/delivery-acceptance", summary="冻结单模块交付验收")
def module_delivery_acceptance(tenant_id: int, module_key: str, body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import module_commerce_lifecycle_service as lifecycle
    return success(lifecycle.accept_module_delivery(user, int(tenant_id), module_key, acceptance_ref=str(body.get("acceptanceRef") or ""), reason=str(body.get("reason") or ""), expected_generation=_required_int(body, "expectedGeneration")), message="模块交付验收已冻结；没有新增授权")


@router.post("/commercial/tenants/{tenant_id}/sources/{source_id}/cancel-at-period-end", summary="计划服务期末停止续费")
def schedule_source_cancel(tenant_id: int, source_id: int, body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import module_commerce_lifecycle_service as lifecycle
    return success(lifecycle.schedule_source_cancellation(user, int(tenant_id), int(source_id), expected_version=_required_int(body, "expectedVersion"), reason=str(body.get("reason") or "")), message="已计划在当前已付服务期结束后停止续费；当前授权不变")


@router.post("/commercial/tenants/{tenant_id}/sources/{source_id}/resume-renewal", summary="撤销计划退订")
def resume_source(tenant_id: int, source_id: int, body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import module_commerce_lifecycle_service as lifecycle
    return success(lifecycle.resume_source_renewal(user, int(tenant_id), int(source_id), expected_plan_version=_required_int(body, "expectedPlanVersion"), reason=str(body.get("reason") or "")), message="计划退订已撤销；不会自动延长已付服务期限")


@router.post("/commercial/tenants/{tenant_id}/sources/{source_id}/cancel", summary="立即取消一个模块订阅来源")
def cancel_source(tenant_id: int, source_id: int, body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import module_subscription_service as subscriptions
    return success(subscriptions.cancel_subscription_source_now(int(tenant_id), int(source_id), expected_version=_required_int(body, "expectedVersion"), reason=str(body.get("reason") or "")), message="该订阅来源已取消；其他有效来源保持不变")


@router.get("/commercial/tenants/{tenant_id}/modules/{module_key}/offboarding-preview", summary="查看单模块退出影响（纯读取）")
def offboarding_preview(tenant_id: int, module_key: str, user=Depends(require_platform_capability("commercial.view"))):
    from app.services import module_commerce_lifecycle_service as lifecycle
    return success(lifecycle.preview_module_offboarding(int(tenant_id), module_key))


@router.post("/commercial/tenants/{tenant_id}/modules/{module_key}/offboarding", summary="发起单模块退出并冻结目标代次")
def request_offboarding(tenant_id: int, module_key: str, body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import module_commerce_lifecycle_service as lifecycle
    return success(lifecycle.request_module_offboarding(user, int(tenant_id), module_key, expected_lifecycle_version=_required_int(body, "expectedLifecycleVersion"), reason=str(body.get("reason") or ""), retention_days=_required_int(body, "retentionDays"), retention_policy_version=str(body.get("retentionPolicyVersion") or "")), message="目标模块已冻结；整校与其他模块保持不变")


@router.get("/commercial/module-offboarding/{job_id}", summary="查看单模块退出任务")
def get_offboarding(job_id: int, user=Depends(require_platform_capability("commercial.view"))):
    from app.services import module_commerce_lifecycle_service as lifecycle
    return success(lifecycle.get_module_offboarding_job(int(job_id)))


@router.post("/commercial/module-offboarding/{job_id}/cancel", summary="不可逆前取消模块退出")
def cancel_offboarding(job_id: int, body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import module_commerce_lifecycle_service as lifecycle
    return success(lifecycle.cancel_module_offboarding(user, int(job_id), expected_version=_required_int(body, "expectedVersion"), reason=str(body.get("reason") or "")), message="模块退出已取消；数据状态已恢复，但不会凭空恢复商业授权")


@router.post("/commercial/module-offboarding/{job_id}/export", summary="绑定并核验最终模块导出")
def bind_export(job_id: int, body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import module_commerce_lifecycle_service as lifecycle
    return success(lifecycle.bind_module_export(user, int(job_id), export_job_id=_required_int(body, "exportJobId"), manifest_id=_required_int(body, "manifestId"), scope_hash=str(body.get("scopeHash") or ""), expected_version=_required_int(body, "expectedVersion")), message="最终导出已通过服务端任务、Manifest与文件对象核验，等待校方接收")


@router.post("/commercial/module-offboarding/{job_id}/export-acceptance", summary="校方确认接收并进入保留期")
def accept_export(job_id: int, body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import module_commerce_lifecycle_service as lifecycle
    return success(lifecycle.accept_module_export(user, int(job_id), acceptance_ref=str(body.get("acceptanceRef") or ""), expected_version=_required_int(body, "expectedVersion")), message="校方接收已记录，保留期从本次接收时间起算；未授权物理销毁")


@router.post("/commercial/tenants/{tenant_id}/cutover", summary="单租户切换MODULE_V2商业读取")
def cutover(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import module_subscription_service as subscriptions
    legacy = commercial.legacy_commercial_state_for_reconciliation(int(tenant_id))
    return success(subscriptions.switch_reader_to_module_v2(int(tenant_id), expected_version=_required_int(body, "expectedVersion"), reason=str(body.get("reason") or ""), legacy_features=legacy["features"]), message="商业读取已切换到MODULE_V2")


def install_into_platform_router(target: APIRouter) -> int:
    """Install additive routes atomically; reject collisions, preserve same-object retries.

    The production registration path imports platform_router, not the compatibility
    facade. Installing here during package bootstrap makes both imports observe the
    same guarded endpoints without changing the frozen bundle or replacing PAM.
    """
    from fastapi.routing import APIRoute
    from app.core.commercial_surface_module_gate import iter_effective_route_contexts

    def keys(context):
        # API contexts expose the effective path directly. Included Starlette
        # routes expose their effective route through the same context facade.
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
            raise RuntimeError("Invalid or duplicate module-commerce route declaration")
        declared.update(signatures)
        if all(len(existing.get(key, [])) == 1 and existing[key][0] is route
               for key in signatures):
            continue
        collisions = sorted(key for key in signatures if key in existing)
        if collisions:
            raise RuntimeError(f"Module-commerce route collision: {collisions}")
        pending.append(route)
    # No mutation until every route has passed collision review. Never remove a
    # pre-existing route, silently replace a capability, or add a duplicate handler.
    target.routes.extend(pending)
    return len(pending)
