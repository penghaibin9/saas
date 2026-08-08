"""A5 / P0-07：平台运营正式依赖图必须退出浏览器 mock 事实源。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / "frontend" / "src" / "modules" / "platform"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
    for src in (layout, dashboard):
        assert "platform.api" not in src
        assert "platformApi" not in src
    assert "platformControlApi.getContext()" in layout
    assert "ErrorState" in layout and "loadContext" in layout
    assert "PlatformControlOverview" in dashboard


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


def test_pure_mock_platform_api_is_not_reachable_from_formal_entry_views():
    formal_entries = [
        FRONT / "views" / "AdminPlatformLayout.vue",
        FRONT / "views" / "PlatformDashboardView.vue",
        FRONT / "views" / "PlatformIntegrationView.vue",
        FRONT / "views" / "PlatformApiAccessView.vue",
        FRONT / "views" / "PlatformSyncTaskView.vue",
    ]
    combined = "\n".join(_read(p) for p in formal_entries)
    assert "@/modules/platform/api/platform.api" not in combined
    assert "@/mocks/platform" not in combined
