"""S0/B0 contract: owner relocation preserves route surface while adapters harden semantics."""
from __future__ import annotations


def _route_contract(router):
    out = []
    for route in router.routes:
        methods = tuple(sorted(getattr(route, "methods", set()) or set()))
        out.append((getattr(route, "path", ""), methods, getattr(route, "name", "")))
    return tuple(out)


def test_system_facade_exports_control_plane_router_with_same_surface():
    from app.api.v1 import system as legacy
    from app.modules.system_admin.routers import system_bundle, system_router

    assert legacy.router is system_router.router
    assert _route_contract(legacy.router) == _route_contract(system_bundle.router)
    assert legacy.copy_system_role is system_router.copy_system_role
    assert legacy.save_system_role_permissions is system_router.save_system_role_permissions
    assert legacy.reset_system_user_password is system_bundle.reset_system_user_password


def test_platform_legacy_facade_exports_canonical_router():
    from app.api.v1 import platform as legacy
    from app.modules.platform.routers import platform_bundle

    assert legacy.router is platform_bundle.router
    assert legacy.require_platform_super_admin is platform_bundle.require_platform_super_admin
