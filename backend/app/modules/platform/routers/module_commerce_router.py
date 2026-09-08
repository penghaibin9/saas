"""M1/M2 module-commerce control-plane API.

Kept outside the byte-frozen platform bundle. Runtime authority remains the
commercial entitlement facade; these commands only publish catalogue facts,
create itemized orders, inspect/cancel sources, and perform explicit cutover.
"""
from fastapi import APIRouter, Body, Depends, Header

from app.core.response import success
from app.modules.platform.routers.platform_router import require_platform_capability

router = APIRouter(prefix="/platform", tags=["16·平台主管·模块商业化"])


@router.post("/commercial/skus", summary="发布不可变模块SKU")
def publish_sku(body: dict = Body(...), user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import commercial_catalog_service as catalogue
    payload = body.get("sku") if isinstance(body.get("sku"), dict) else body
    out = catalogue.publish_sku(payload, reason=str(body.get("reason") or ""), actor_id=user.get("userId"))
    return success(out, message="商品版本已发布；尚未给任何学校授权")


@router.post("/commercial/orders", summary="创建模块分项订单")
def create_order(body: dict = Body(...), idempotency_key: str = Header(..., alias="Idempotency-Key"),
                 user=Depends(require_platform_capability("order.manage"))):
    from app.services import commercial_order_item_service as orders
    out = orders.create_itemized_order(body, idempotency_key=idempotency_key, actor_id=user.get("userId") or "0")
    return success(out, message="分项订单已创建（未支付、未授权）")


@router.get("/commercial/tenants/{tenant_id}/projection", summary="查看商业授权唯一投影")
def projection(tenant_id: int, user=Depends(require_platform_capability("commercial.view"))):
    from app.services import commercial_entitlement_authority_service as commercial
    return success(commercial.commercial_state(int(tenant_id)))


@router.get("/commercial/tenants/{tenant_id}/shadow", summary="查看LEGACY与MODULE_V2影子差异")
def shadow(tenant_id: int, user=Depends(require_platform_capability("commercial.view"))):
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import module_subscription_service as subscriptions
    legacy = commercial.legacy_commercial_state_for_reconciliation(int(tenant_id))
    out = subscriptions.shadow_reconcile_tenant(int(tenant_id), legacy_features=legacy["features"])
    out["legacyAuthoritySource"] = legacy.get("authoritySource")
    out["migrationClassification"] = subscriptions.classify_legacy_authority(legacy)
    return success(out)


@router.post("/commercial/tenants/{tenant_id}/sources/{source_id}/cancel", summary="取消一个模块订阅来源")
def cancel_source(tenant_id: int, source_id: int, body: dict = Body(...),
                  user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import module_subscription_service as subscriptions
    out = subscriptions.cancel_subscription_source_now(
        int(tenant_id), int(source_id), expected_version=int(body.get("expectedVersion")),
        reason=str(body.get("reason") or ""),
    )
    return success(out, message="该订阅来源已取消；其他有效来源保持不变")


@router.post("/commercial/tenants/{tenant_id}/cutover", summary="单租户切换MODULE_V2商业读取")
def cutover(tenant_id: int, body: dict = Body(...),
            user=Depends(require_platform_capability("commercial.manage"))):
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import module_subscription_service as subscriptions
    legacy = commercial.legacy_commercial_state_for_reconciliation(int(tenant_id))
    out = subscriptions.switch_reader_to_module_v2(
        int(tenant_id), expected_version=int(body.get("expectedVersion")),
        reason=str(body.get("reason") or ""), legacy_features=legacy["features"],
    )
    return success(out, message="商业读取已切换到MODULE_V2")
