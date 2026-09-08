from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.core.exceptions import AppException
from app.core.commercial_surface_module_gate import (
    enforce_commercial_surface_access,
    module_for_surface,
)


def _request(method: str, path: str) -> Request:
    return Request({
        "type": "http", "http_version": "1.1", "method": method,
        "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [],
        "client": ("127.0.0.1", 1234), "server": ("127.0.0.1", 8000),
    })


@pytest.mark.parametrize(("path", "module"), [
    ("/api/v1/mobile/affairs/leaves/1", "studentAffairs"),
    ("/api/v1/mobile/teacher/affairs/activities/ongoing", "studentAffairs"),
    ("/api/v1/mobile/campus-service/apply", "studentAffairs"),
    ("/api/v1/portal/affairs/fee-reductions", "studentAffairs"),
    ("/api/v1/mobile/me/psy-survey/submit", "studentAffairs"),
    ("/api/v1/mobile/academic/status-changes/7/resubmit", "academicAffairs"),
    ("/api/v1/mobile/teacher/academic/status-changes/pending", "academicAffairs"),
    ("/api/v1/portal/academic/exam/defer/9/resubmit", "academicAffairs"),
    ("/api/v1/portal/graduation/taskbook/sign", "graduationDesign"),
    ("/api/v1/mobile/graduation/final", "graduationDesign"),
    ("/api/v1/internship/dashboard", "internship"),
    ("/api/v1/portal/internship/applications", "internship"),
])
def test_known_business_surface_maps_to_canonical_product(path, module):
    assert module_for_surface(path) == module


@pytest.mark.parametrize("path", [
    "/api/v1/auth/login",
    "/api/v1/mobile/orientation/batch-status",
    "/api/v1/platform/commercial/tenants/1/modules",
    "/api/v1/mobile/me/profile",
    "/api/v1/mobile/performance/teacher/workbench",
    "/health",
])
def test_public_or_cross_product_surface_is_not_accidentally_gated(path):
    assert module_for_surface(path) is None


def test_final_api_graph_gate_covers_late_supplemental_routes():
    from app.api.v1.router import api_router
    from fastapi.routing import APIRoute

    targets = {
        "/mobile/teacher/affairs/activities/ongoing",
        "/mobile/academic/status-changes/{change_id}/resubmit",
        "/portal/graduation/taskbook/sign",
    }
    found = set()
    for route in api_router.routes:
        if not isinstance(route, APIRoute) or route.path not in targets:
            continue
        found.add(route.path)
        calls = {getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies}
        assert "enforce_commercial_surface_access" in calls, route.path
    assert found == targets


def test_platform_super_admin_does_not_bypass_tenant_commercial_truth(monkeypatch):
    from app.core import commercial_surface_module_gate as gate
    from app.core.context import set_current_user, set_tenant
    from app.db import session as db_session
    from app.services import module_access_service

    set_current_user({
        "userId": "db-1", "userType": "PLATFORM_SUPER_ADMIN",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN", "tenantId": "77881",
    })
    set_tenant({"tenantId": "77881", "tenantCode": "surface-super"})
    monkeypatch.setattr(db_session, "db_enabled", lambda: True)
    calls = []

    def deny(tid, module, *, write=False):
        calls.append((tid, module, write))
        raise AppException("NO_PERMISSION", "学校未购买该模块", http_status=403)

    monkeypatch.setattr(module_access_service, "assert_module_access", deny)
    with pytest.raises(AppException) as caught:
        enforce_commercial_surface_access(
            _request("POST", "/api/v1/mobile/academic/status-change")
        )
    assert caught.value.http_status == 403
    assert calls == [(77881, "academicAffairs", True)]


def test_unmapped_platform_super_admin_request_stays_outside_school_module_gate(monkeypatch):
    from app.core.context import set_current_user, set_tenant
    from app.db import session as db_session
    from app.services import module_access_service

    set_current_user({"userId": "db-1", "userType": "PLATFORM_SUPER_ADMIN"})
    set_tenant(None)
    monkeypatch.setattr(db_session, "db_enabled", lambda: True)
    marker = []
    monkeypatch.setattr(module_access_service, "assert_module_access", lambda *a, **k: marker.append(1))
    assert enforce_commercial_surface_access(
        _request("GET", "/api/v1/platform/commercial/tenants/1/modules")
    ) is None
    assert marker == []
