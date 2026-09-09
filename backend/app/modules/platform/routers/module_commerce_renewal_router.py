"""M8 renewal follow-up bridge.

This surface is additive to frozen M1-M5, M8 finance and M8 operations. It can create
an existing customer-success RenewalTask, but never creates a sales order, charges money
or mutates entitlement.
"""
from fastapi import APIRouter, Body, Depends, Query
from app.core.response import success
from app.modules.platform.routers.platform_router import require_platform_capability

router=APIRouter(prefix="/platform",tags=["16·平台主管·商业续费治理"])

@router.get("/commercial/tenants/{tenant_id}/renewal-candidates",summary="读取当前代次最晚已付来源续费候选")
def renewal_candidates(tenant_id:int,withinDays:int=Query(120,ge=1,le=3650),page:int=Query(1,ge=1,le=10000),pageSize:int=Query(20,ge=1,le=100),user=Depends(require_platform_capability("commercial.view"))):
    from app.services import module_commerce_renewal_service as renewal
    return success(renewal.list_renewal_candidates(int(tenant_id),within_days=withinDays,page=page,page_size=pageSize))

@router.post("/commercial/tenants/{tenant_id}/sources/{source_id}/renewal-followup",summary="把已付来源显式交给现有客户成功续费任务")
def renewal_followup(tenant_id:int,source_id:int,body:dict=Body(...),user=Depends(require_platform_capability("customerSuccess.manage"))):
    from app.services import module_commerce_renewal_service as renewal
    return success(renewal.ensure_renewal_followup(user,int(tenant_id),int(source_id),due_at=body.get("dueAt"),owner_name=str(body.get("ownerName") or ""),note=str(body.get("note") or "")),
                   message="续费候选已交给现有客户成功 RenewalTask；未创建订单、未扣款、未修改模块授权")

def install_into_platform_router(target:APIRouter)->int:
    from fastapi.routing import APIRoute
    from app.core.commercial_surface_module_gate import iter_effective_route_contexts
    def keys(context):
        leaf=getattr(context,"route",context); fallback=getattr(context,"starlette_route",None) or leaf
        path=getattr(context,"path",None) or getattr(fallback,"path",""); methods=getattr(context,"methods",None) or getattr(fallback,"methods",None) or ()
        return {(str(method).upper(),path) for method in methods}
    existing={}
    for context in iter_effective_route_contexts(target):
        route=getattr(context,"route",context)
        for key in keys(context): existing.setdefault(key,[]).append(route)
    declared=set(); pending=[]
    for route in router.routes:
        signatures=keys(route)
        if not isinstance(route,APIRoute) or not signatures or declared & signatures: raise RuntimeError("Invalid or duplicate module-commerce renewal route declaration")
        declared.update(signatures)
        if all(len(existing.get(key,[]))==1 and existing[key][0] is route for key in signatures): continue
        collisions=sorted(key for key in signatures if key in existing)
        if collisions: raise RuntimeError(f"Module-commerce renewal route collision: {collisions}")
        pending.append(route)
    target.routes.extend(pending); return len(pending)
