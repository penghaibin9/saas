"""P1：租户只读守卫 fail-closed。"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from starlette.requests import Request

from app.middleware.context import _demo_tenant_readonly_deny, _expired_tenant_readonly_deny


def _req(method: str, path: str = "/api/v1/students") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _enable_demo_readonly(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.DEMO_TENANT_READONLY", "true")


def test_demo_tenant_write_forbidden():
    with patch("app.core.context.get_tenant", return_value={"tenantId": "1000000000000000003"}):
        with patch("app.services.audit_log.record"):
            resp = _demo_tenant_readonly_deny(_req("POST"))
    assert resp is not None
    assert resp.status_code == 403


def test_get_still_allowed_for_demo_tenant():
    with patch("app.core.context.get_tenant", return_value={"tenantId": "1000000000000000003"}):
        assert _demo_tenant_readonly_deny(_req("GET")) is None


def test_demo_guard_exception_on_write_returns_503():
    with patch("app.core.context.get_tenant", side_effect=RuntimeError("boom")):
        resp = _demo_tenant_readonly_deny(_req("PUT"))
    assert resp is not None
    assert resp.status_code == 503
    body = resp.body
    assert b"TENANT_GUARD_UNAVAILABLE" in body


def test_expired_tenant_write_403():
    with patch("app.core.context.get_current_user_ctx", return_value={"userId": "u1", "userType": "TEACHER"}):
        with patch("app.core.context.get_tenant", return_value={"tenantId": "9"}):
            with patch("app.db.session.db_enabled", return_value=True):
                with patch("app.services.platform_service.tenant_status", return_value="expired"):
                    with patch("app.services.audit_log.record"):
                        resp = _expired_tenant_readonly_deny(_req("DELETE"))
    assert resp is not None
    assert resp.status_code == 403


def test_tenant_status_service_error_write_503():
    with patch("app.core.context.get_current_user_ctx", return_value={"userId": "u1"}):
        with patch("app.core.context.get_tenant", return_value={"tenantId": "9"}):
            with patch("app.db.session.db_enabled", return_value=True):
                with patch("app.services.platform_service.tenant_status",
                           side_effect=RuntimeError("db down")):
                    resp = _expired_tenant_readonly_deny(_req("POST"))
    assert resp is not None
    assert resp.status_code == 503


def test_expired_get_still_ok():
    assert _expired_tenant_readonly_deny(_req("GET")) is None


def test_platform_super_admin_exempt_when_verified():
    user = {"userId": "db-1", "userType": "PLATFORM_SUPER_ADMIN", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}
    with patch("app.core.context.get_current_user_ctx", return_value=user):
        with patch("app.core.context.get_tenant", return_value={"tenantId": "9"}):
            with patch("app.db.session.db_enabled", return_value=True):
                with patch("app.services.platform_service.tenant_status", return_value="expired"):
                    assert _expired_tenant_readonly_deny(_req("POST")) is None


def test_bogus_super_admin_claim_without_userid_not_exempt():
    """非法/空身份不得借超管路径绕过。"""
    user = {"userType": "PLATFORM_SUPER_ADMIN"}  # 无 userId
    with patch("app.core.context.get_current_user_ctx", return_value=user):
        with patch("app.core.context.get_tenant", return_value={"tenantId": "9"}):
            with patch("app.db.session.db_enabled", return_value=True):
                with patch("app.services.platform_service.tenant_status", return_value="expired"):
                    with patch("app.services.audit_log.record"):
                        resp = _expired_tenant_readonly_deny(_req("POST"))
    assert resp is not None
    assert resp.status_code == 403
