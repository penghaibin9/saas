"""S0 Move Only contract: owner relocation must not change runtime routers."""
from __future__ import annotations


def test_system_legacy_facade_exports_canonical_router():
    from app.api.v1 import system as legacy
    from app.modules.system_admin.routers import system_bundle

    assert legacy.router is system_bundle.router
    assert legacy.assign_system_user_roles is system_bundle.assign_system_user_roles
    assert legacy.save_system_role_permissions is system_bundle.save_system_role_permissions
    assert legacy.reset_system_user_password is system_bundle.reset_system_user_password


def test_platform_legacy_facade_exports_canonical_router():
    from app.api.v1 import platform as legacy
    from app.modules.platform.routers import platform_bundle

    assert legacy.router is platform_bundle.router
    assert legacy.require_platform_super_admin is platform_bundle.require_platform_super_admin


def _route_contract(router):
    out = []
    for route in router.routes:
        methods = tuple(sorted(getattr(route, "methods", set()) or set()))
        out.append((getattr(route, "path", ""), methods, getattr(route, "name", "")))
    return tuple(out)


def test_facade_and_canonical_route_contracts_are_identical():
    from app.api.v1 import platform as legacy_platform
    from app.api.v1 import system as legacy_system
    from app.modules.platform.routers import platform_bundle
    from app.modules.system_admin.routers import system_bundle

    assert _route_contract(legacy_system.router) == _route_contract(system_bundle.router)
    assert _route_contract(legacy_platform.router) == _route_contract(platform_bundle.router)
