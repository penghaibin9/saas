"""Platform Control Plane adapters layered over the byte-frozen platform bundle."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.platform_assurance import assurance_state, assert_recent_platform_auth
from app.core.platform_principal import require_platform_principal
from app.core.response import paginate, success
from app.modules.platform.routers import platform_bundle as _bundle
from app.modules.platform.routers import product_iam_router as _product_iam

_routes = APIRouter(prefix="/platform", tags=["16·平台控制面"])


def _pam():
    from app.services import platform_access_governance_service as pam
    return pam


def _cap(user: dict, capability: str) -> dict:
    return _pam().assert_platform_capability(user, capability)


@_routes.get("/context", summary="平台主管 identity-first 上下文")
def platform_context(user=Depends(require_platform_principal)):
    pam = _pam()
    uid = str(user.get("userId") or "")
    elevations = [item for item in pam.list_records(pam.ELEVATION) if str(item.get("userId")) == uid and str(item.get("status") or "ACTIVE").upper() == "ACTIVE"]
    supports = [item for item in pam.list_records(pam.SUPPORT) if str(item.get("operatorUserId")) == uid and str(item.get("status") or "ACTIVE").upper() == "ACTIVE"]
    state = assurance_state(user)
    return success({
        "principalPlane": "PLATFORM",
        "subjectId": uid,
        "roleCode": user.get("currentRoleCode") or user.get("userType"),
        "duties": sorted(pam.effective_platform_duties(user)),
        "temporaryElevations": elevations,
        "supportScopeSummary": [{"tenantId": item.get("tenantId"), "scopes": item.get("scopes"), "expiresAt": item.get("expiresAt")} for item in supports],
        "recentAuthState": {"recent": state["recent"], "ageSeconds": state["ageSeconds"], "maxAgeSeconds": state["maxAgeSeconds"]},
        "mfaAssurance": {"satisfied": state["mfa"], "amr": state["amr"], "acr": state["acr"], "source": state["source"]},
    })


@_routes.get("/access-assignments", summary="平台职责分配")
def access_assignments(user=Depends(require_platform_principal)):
    _cap(user, "access.review")
    return success({"items": _pam().list_records(_pam().ASSIGNMENT)})


@_routes.post("/access-assignments", summary="保存平台职责分配")
def access_assignment_save(body: dict = Body(...), user=Depends(require_platform_principal)):
    _cap(user, "access.manage")
    return success(_pam().save_access_assignment(body, actor=user))


@_routes.get("/elevation-sessions", summary="临时权限提升会话")
def elevation_sessions(user=Depends(require_platform_principal)):
    _cap(user, "access.review")
    return success({"items": _pam().list_records(_pam().ELEVATION)})


@_routes.post("/elevation-sessions", summary="创建自动到期的临时提升")
def elevation_session_create(body: dict = Body(...), user=Depends(require_platform_principal)):
    _cap(user, "access.manage")
    return success(_pam().create_elevation(body, actor=user))


@_routes.get("/support-sessions", summary="受控学校协助会话")
def support_sessions(tenantId: int | None = Query(default=None), user=Depends(require_platform_principal)):
    pam = _pam()
    uid = str(user.get("userId") or "")
    role = str(user.get("currentRoleCode") or user.get("userType") or "").upper()
    review_all = role in {"PLATFORM_OWNER", "PLATFORM_SUPER_ADMIN", "PLATFORM_SECURITY_AUDITOR"}
    if tenantId is not None:
        _cap(user, "support.request")
        rows = pam.list_records(pam.SUPPORT, tenant_id=tenantId)
        if not review_all:
            rows = [row for row in rows if str(row.get("operatorUserId")) == uid]
    elif review_all:
        rows = pam.list_records(pam.SUPPORT)
    else:
        _cap(user, "support.request")
        rows = [row for row in pam.list_records(pam.SUPPORT) if str(row.get("operatorUserId")) == uid]
    return success({"items": rows, "visibility": "REVIEW_ALL" if review_all else "OWN"})


@_routes.post("/support-sessions", summary="创建绑定真实 Incident 的受控协助")
def support_session_create(body: dict = Body(...), user=Depends(require_platform_principal)):
    _cap(user, "support.request")
    return success(_pam().create_support_session(body, actor=user))


@_routes.post("/support-sessions/{session_id}/terminate", summary="显式终止受控协助")
def support_session_terminate(session_id: str, body: dict = Body(...), user=Depends(require_platform_principal)):
    _cap(user, "support.request")
    out = _pam().terminate_record(
        _pam().SUPPORT, session_id,
        tenant_id=int(body.get("tenantId") or 0),
        expected_version=int(body.get("expectedVersion") or -1),
        reason=body.get("reason") or "",
        actor=user,
    )
    return success(out)


@_routes.get("/support/tenants/{tenant_id}/context", summary="受控协助：学校支持上下文")
def support_tenant_context(tenant_id: int, user=Depends(require_platform_principal)):
    pam = _pam()
    _cap(user, "support.request")
    pam.assert_support_session(user, tenant_id=tenant_id, scope="tenant.context.read")
    from app.services import platform_service as svc
    tenant = svc.get_tenant(tenant_id)
    return success({k: tenant.get(k) for k in ("tenantId", "tenantCode", "tenantName", "status", "expireAt", "studentCount", "userCount")})


@_routes.get("/support/tenants/{tenant_id}/audit", summary="受控协助：学校审计摘要")
def support_tenant_audit(tenant_id: int, page: int = Query(default=1, ge=1), pageSize: int = Query(default=20, ge=1, le=100), user=Depends(require_platform_principal)):
    pam = _pam()
    _cap(user, "support.request")
    pam.assert_support_session(user, tenant_id=tenant_id, scope="tenant.audit.read")
    assert_recent_platform_auth(user, require_mfa=True)
    from app.services import platform_service as svc
    items, total = svc.platform_audit_query(page, pageSize, tenant_id=tenant_id)
    return success(paginate(items, total, page, pageSize))


@_routes.post("/access-reviews", summary="创建平台主管访问复核活动")
def access_review_create(body: dict = Body(...), user=Depends(require_platform_principal)):
    _cap(user, "access.review")
    return success(_pam().create_access_review(body, actor=user))


@_routes.get("/access-reviews", summary="平台主管访问复核活动")
def access_reviews(user=Depends(require_platform_principal)):
    _cap(user, "access.review")
    return success({"items": _pam().list_records(_pam().REVIEW)})


@_routes.post("/access-reviews/{review_id}/close", summary="关闭访问复核并原子撤销选中 grant")
def access_review_close(review_id: str, body: dict = Body(...), user=Depends(require_platform_principal)):
    _cap(user, "access.review")
    return success(_pam().close_access_review(review_id, body, actor=user))


def _route_key(route) -> tuple[str, str]:
    methods = sorted(getattr(route, "methods", set()) or set())
    return (methods[0] if len(methods) == 1 else ",".join(methods), getattr(route, "path", ""))


def _compose_router() -> APIRouter:
    replacement = {_route_key(route): route for route in _routes.routes}
    composed = APIRouter()
    routes = []
    for route in _bundle.router.routes:
        key = _route_key(route)
        routes.append(replacement.pop(key, route))
    routes.extend(replacement.values())
    product_keys = {_route_key(route) for route in _product_iam.router.routes}
    existing_keys = {_route_key(route) for route in routes}
    collisions = sorted(product_keys & existing_keys)
    if collisions:
        raise RuntimeError(f"Product IAM route collision: {collisions}")
    routes.extend(_product_iam.router.routes)
    composed.routes = routes
    return composed


router = _compose_router()
