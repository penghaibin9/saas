"""S0/B0 contract: owner relocation preserves frozen route surface while adapters harden semantics."""
from __future__ import annotations


def _route_key(route):
    methods = tuple(sorted(getattr(route, "methods", set()) or set()))
    return (getattr(route, "path", ""), methods)


def _route_keys(router):
    return tuple(_route_key(route) for route in router.routes)


def test_system_facade_exports_final_composed_router_and_preserves_frozen_surface():
    from app.api.v1 import system as legacy
    from app.modules.system_admin.routers import system_bundle, system_i4_router, system_router

    # Runtime facade must expose the final composition (B0-B7 + I1/I2 + I4),
    # not the frozen bundle alone. S0 compatibility means every legacy
    # method/path remains represented while approved adapters may replace the
    # APIRoute object or add new Control Plane endpoints.
    assert legacy.router is system_i4_router.router
    frozen = set(_route_keys(system_bundle.router))
    final = _route_keys(legacy.router)
    assert frozen <= set(final)
    assert len(final) == len(set(final))

    assert legacy.copy_system_role is system_router.copy_system_role
    assert legacy.save_system_role_permissions is system_router.save_system_role_permissions
    assert legacy.reset_system_user_password is system_bundle.reset_system_user_password

    assert ("/system/iam/summary", ("GET",)) in set(final)
    assert ("/system/roles/{role_id}/members", ("GET",)) in set(final)
    assert ("/system/roles/{role_id}/audit", ("GET",)) in set(final)


def test_platform_legacy_facade_exports_final_composed_router_and_preserves_frozen_surface():
    from app.api.v1 import platform as legacy
    from app.modules.platform.routers import platform_bundle, platform_router

    assert legacy.router is platform_router.router
    frozen = set(_route_keys(platform_bundle.router))
    final = _route_keys(legacy.router)
    assert frozen <= set(final)
    assert len(final) == len(set(final))

    assert legacy.require_platform_super_admin is platform_bundle.require_platform_super_admin
    assert legacy.platform_context is platform_router.platform_context
    assert ("/platform/context", ("GET",)) in set(final)
    assert ("/platform/product-iam/source", ("GET",)) in set(final)
