from __future__ import annotations

import pytest

from app.core.exceptions import AppException


def _dependency():
    from app.api.v1 import student_portal_graduation_guard as portal
    assert portal.router.dependencies, "student graduation portal must have a router-level module gate"
    return portal.router.dependencies[0].dependency


def _install_gate_context(monkeypatch, tenant_id: int = 99001):
    from app.core.context import set_tenant
    from app.db import session as db_session
    from app.services import module_access_service

    set_tenant({"tenantId": str(tenant_id), "tenantCode": f"portal-{tenant_id}"})
    monkeypatch.setattr(db_session, "db_enabled", lambda: True)
    calls = []
    monkeypatch.setattr(
        module_access_service,
        "assert_module_access",
        lambda tid, key, *, write=False: calls.append((tid, key, write)) or {"allowed": True},
    )
    return calls


def test_student_graduation_portal_router_uses_canonical_module_gate(monkeypatch):
    calls = _install_gate_context(monkeypatch)
    user = {"userId": "student-1", "userType": "STUDENT", "tenantId": "99001"}
    assert _dependency()(user=user) is user
    assert calls == [(99001, "graduation", False)]


def test_student_graduation_portal_unpurchased_or_frozen_module_is_not_bypassed(monkeypatch):
    _install_gate_context(monkeypatch, tenant_id=99002)
    from app.services import module_access_service

    def deny(*_args, **_kwargs):
        raise AppException("NO_PERMISSION", "毕业设计模块未购买或已冻结", http_status=403)

    monkeypatch.setattr(module_access_service, "assert_module_access", deny)
    with pytest.raises(AppException) as caught:
        _dependency()(user={"userId": "student-2", "userType": "STUDENT", "tenantId": "99002"})
    assert caught.value.http_status == 403


def test_all_high_risk_student_graduation_routes_inherit_router_dependency():
    from app.api.v1 import student_portal_graduation_guard as portal
    expected = {
        "/portal/graduation/taskbook/sign",
        "/portal/graduation/review-feedback",
        "/portal/graduation/extensions/my",
        "/portal/graduation/defense-delay/apply",
        "/portal/graduation/materials/{file_id}/abandon",
    }
    paths = {route.path for route in portal.router.routes}
    assert expected <= paths
    for route in portal.router.routes:
        if route.path in expected:
            dependency_calls = {getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies}
            assert "_dep" in dependency_calls, f"module gate missing from {route.path}"
