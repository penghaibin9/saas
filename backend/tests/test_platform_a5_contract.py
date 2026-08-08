"""A5 / P0-07：平台运营正式依赖图必须退出浏览器 mock 事实源。"""
from pathlib import Path

from app.core.security import create_access_token

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / "frontend" / "src" / "modules" / "platform"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _headers(*, role: str, user_type: str, tenant_id: str) -> dict:
    token = create_access_token({
        "userId": f"a5-{role.lower()}",
        "realName": "A5验收账号",
        "userType": user_type,
        "tid": "platform" if role.startswith("PLATFORM_") else "demo",
        "tenantId": tenant_id,
        "activeContextId": "a5-context",
        "currentRoleCode": role,
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def test_platform_control_facade_is_real_only():
    src = _read(FRONT / "api" / "platformControl.api.js")
    forbidden = (
        "shouldTryReal", "MOCK_TENANTS", "MOCK_OVERVIEW", "mockData",
        "回退演示数据", "ok（演示数据）", "@/mocks/platform",
    )
    for token in forbidden:
        assert token not in src, token
    assert "request('/platform/overview')" in src
    assert "request('/authz/me')" in src
    assert "getContext" in src


def test_formal_parent_and_dashboard_do_not_use_pure_mock_platform_api():
    layout = _read(FRONT / "views" / "AdminPlatformLayout.vue")
    dashboard = _read(FRONT / "views" / "PlatformDashboardView.vue")
    overview = _read(FRONT / "views" / "control" / "PlatformControlOverview.vue")
    for src in (layout, dashboard, overview):
        assert "platform.api" not in src
        assert "platformApi" not in src
    assert "platformControlApi.getContext()" in layout
    assert "ErrorState" in layout and "loadContext" in layout
    assert "PlatformControlOverview" in dashboard
    assert ':ctx="ctx"' in dashboard
    assert "ctx.currentRole.roleName" in overview
    assert "ctx.dataScope.scopeName" in overview


def test_overview_refresh_failure_clears_stale_metrics_before_error_state():
    src = _read(FRONT / "views" / "control" / "PlatformControlOverview.vue")
    assert "this.ov = null" in src
    assert "this.error = ''" in src
    assert 'v-else-if="error"' in src
    assert ':description="error"' in src
    assert "res.message || '平台总览加载失败'" in src


def test_remaining_formal_legacy_routes_are_fail_closed_capability_shells():
    cases = {
        "PlatformIntegrationView.vue": "plt-integrations",
        "PlatformApiAccessView.vue": "plt-api-access",
        "PlatformSyncTaskView.vue": "plt-operations",
    }
    for filename, capability_key in cases.items():
        src = _read(FRONT / "views" / filename)
        assert "platform.api" not in src, filename
        assert "platformApi" not in src, filename
        assert "PlatformCapabilityView" in src, filename
        assert capability_key in src, filename


def test_capability_shell_has_no_executable_fake_business_action():
    src = _read(FRONT / "views" / "PlatformCapabilityView.vue")
    assert "capabilityKey" in src
    assert "未接真实 API 的能力仅展示合同与边界" in src
    assert "@click" not in src
    assert "toast." not in src


def test_formal_route_graph_does_not_reconnect_superseded_mock_crud_pages():
    routes = _read(FRONT / "platform.routes.js")
    dead_mock_pages = (
        "PlatformTenantListView.vue",
        "PlatformTenantDetailView.vue",
        "PlatformPackageView.vue",
        "PlatformOrderView.vue",
    )
    for page in dead_mock_pages:
        assert page not in routes, page
    assert "PlatformControlTenants.vue" in routes
    assert "PlatformControlTenantDetail.vue" in routes
    assert "PlatformControlPackages.vue" in routes
    assert "PlatformControlOrders.vue" in routes


def test_pure_mock_platform_api_is_not_reachable_from_formal_entry_views():
    formal_entries = [
        FRONT / "views" / "AdminPlatformLayout.vue",
        FRONT / "views" / "PlatformDashboardView.vue",
        FRONT / "views" / "PlatformIntegrationView.vue",
        FRONT / "views" / "PlatformApiAccessView.vue",
        FRONT / "views" / "PlatformSyncTaskView.vue",
        FRONT / "views" / "control" / "PlatformControlOverview.vue",
    ]
    combined = "\n".join(_read(p) for p in formal_entries)
    assert "@/modules/platform/api/platform.api" not in combined
    assert "@/mocks/platform" not in combined


def test_platform_backend_guard_blocks_school_role_even_if_url_is_called_directly(client, db_mode):
    owner = _headers(role="PLATFORM_SUPER_ADMIN", user_type="PLATFORM_SUPER_ADMIN", tenant_id="0")
    school = _headers(role="SCHOOL_ADMIN", user_type="ADMIN", tenant_id="1000000000000000001")

    allowed = client.get("/api/v1/platform/overview", headers=owner)
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["code"] == 0

    denied = client.get("/api/v1/platform/overview", headers=school)
    assert denied.status_code == 403, denied.text
    assert denied.json()["bizCode"] == "NO_PERMISSION"
