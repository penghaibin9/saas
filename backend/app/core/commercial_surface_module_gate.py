"""Canonical commercial-module gate for standard JWT business surfaces.

Route bundles in this repository are assembled from both include_router() and late
APIRoute append operations. Relying only on per-router dependencies therefore leaves
new mobile/portal/supplemental endpoints easy to miss. This dependency is installed
once on the final API router and maps only known product surfaces to the four
commercial module instances. Unmapped/public platform surfaces are untouched.
"""
from __future__ import annotations

from fastapi import Request

from app.core.exceptions import AppException

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_PUBLIC_EXACT = frozenset({
    "/api/v1/mobile/orientation/batch-status",
})
_PUBLIC_PREFIXES = (
    "/api/v1/internship/enterprise-portal/auth/",
)

# Longest/specific prefixes first.  Orientation and campus-service are capabilities
# sold inside the canonical studentAffairs product; freezing that product must also
# stop those independent historical surfaces.
_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/api/v1/mobile/me/psy-survey", "studentAffairs"),
    ("/api/v1/mobile/teacher/campus-service", "studentAffairs"),
    ("/api/v1/mobile/teacher/orientation", "studentAffairs"),
    ("/api/v1/mobile/teacher/affairs", "studentAffairs"),
    ("/api/v1/mobile/teacher/academic", "academicAffairs"),
    ("/api/v1/mobile/teacher/internship", "internship"),
    ("/api/v1/mobile/teacher/graduation", "graduationDesign"),
    ("/api/v1/mobile/campus-service", "studentAffairs"),
    ("/api/v1/mobile/orientation", "studentAffairs"),
    ("/api/v1/mobile/affairs", "studentAffairs"),
    ("/api/v1/mobile/academic", "academicAffairs"),
    ("/api/v1/mobile/internship", "internship"),
    ("/api/v1/mobile/graduation", "graduationDesign"),
    ("/api/v1/portal/campus-service", "studentAffairs"),
    ("/api/v1/portal/orientation", "studentAffairs"),
    ("/api/v1/portal/affairs", "studentAffairs"),
    ("/api/v1/portal/academic", "academicAffairs"),
    ("/api/v1/portal/internship", "internship"),
    ("/api/v1/portal/graduation", "graduationDesign"),
    ("/api/v1/student-affairs", "studentAffairs"),
    ("/api/v1/campus-service", "studentAffairs"),
    ("/api/v1/orientation", "studentAffairs"),
    ("/api/v1/affairs", "studentAffairs"),
    ("/api/v1/academic-affairs", "academicAffairs"),
    ("/api/v1/academic", "academicAffairs"),
    ("/api/v1/internship", "internship"),
    ("/api/v1/graduation", "graduationDesign"),
)


def module_for_surface(path: str) -> str | None:
    value = str(path or "").rstrip("/") or "/"
    if value in _PUBLIC_EXACT or any(value.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
        return None
    for prefix, module in _PREFIXES:
        if value == prefix or value.startswith(prefix + "/"):
            return module
    return None


def enforce_commercial_surface_access(request: Request) -> None:
    """Gate a mapped authenticated business surface; leave public/unmapped routes alone."""
    module = module_for_surface(request.url.path)
    if module is None:
        return None

    from app.core.context import get_current_user_ctx, get_tenant
    user = get_current_user_ctx() or {}
    # Invalid/missing bearer tokens remain the normal auth dependency's responsibility.
    # This avoids turning public or malformed-token handling into a second auth stack.
    if not user.get("userId"):
        return None

    tenant = get_tenant() or {}
    raw_tid = tenant.get("tenantId") or user.get("tenantId")
    try:
        if isinstance(raw_tid, bool):
            raise ValueError
        tenant_id = int(raw_tid)
        if tenant_id <= 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise AppException(
            "TENANT_CONTEXT_REQUIRED",
            "业务模块请求缺少有效学校上下文，已拒绝访问",
            http_status=403,
        ) from None

    from app.db.session import db_enabled
    if not db_enabled():
        return None

    from app.services.module_access_service import assert_module_access
    assert_module_access(
        tenant_id,
        module,
        write=request.method.upper() not in _SAFE_METHODS,
    )
    return None


def install_on_router(router) -> int:
    """Attach the dependency to final APIRoutes, including late-appended supplements."""
    from fastapi import Depends
    from fastapi.dependencies.utils import get_parameterless_sub_dependant
    from fastapi.routing import APIRoute

    added = 0
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        if any(getattr(dep.call, "__name__", "") == "enforce_commercial_surface_access"
               for dep in route.dependant.dependencies):
            continue
        marker = Depends(enforce_commercial_surface_access)
        route.dependencies.append(marker)
        route.dependant.dependencies.insert(
            0,
            get_parameterless_sub_dependant(depends=marker, path=route.path_format),
        )
        added += 1
    return added
