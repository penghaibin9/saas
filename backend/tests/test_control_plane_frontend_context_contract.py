from pathlib import Path


def test_system_frontend_preserves_effective_access_compat_projection():
    root = Path(__file__).resolve().parents[2]
    api_source = (root / "frontend/src/modules/system/api/system.api.js").read_text(encoding="utf-8")
    router_source = (root / "backend/app/modules/system_admin/routers/system_router.py").read_text(encoding="utf-8")
    assert "permissionActions: data.permissionActions || {}" in api_source
    assert 'actions["effectiveAccess"]' in router_source
    assert '"moduleEntitlements"' in router_source
    assert '"moduleAccessHealthy"' in router_source
    assert '"securityRevision"' in router_source
    assert '"ctxKey"' in router_source
