"""Production-truth contracts for tenant identity, browser auth transport and Python freeze."""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import Response
from starlette.requests import Request

from app.api.v1 import auth_browser
from app.core import tenant_context
from app.core.exceptions import AppException
from app.core.tenant_identity import (
    DEMO_SCHOOL,
    DISABLED_SCHOOL,
    EXPIRED_SCHOOL,
    PLATFORM,
    PRIMARY_DEMO,
    SANDBOX_SCHOOL,
    TRIAL_SCHOOL,
    WELL_KNOWN_BY_CODE,
)
from app.middleware import context as context_middleware

ROOT = Path(__file__).resolve().parents[2]


def _request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/api/v1/authz/me",
            "raw_path": b"/api/v1/authz/me",
            "query_string": b"",
            "headers": headers or [],
            "client": ("127.0.0.1", 12345),
            "server": ("example.test", 443),
        }
    )


def test_well_known_tenant_registry_has_one_unambiguous_identity_per_slot():
    assert PLATFORM.tenant_id == 1000000000000000000
    assert PRIMARY_DEMO.tenant_id == 1000000000000000001
    assert DEMO_SCHOOL.tenant_id == 1000000000000000003
    assert TRIAL_SCHOOL.tenant_id == 1000000000000000004
    assert EXPIRED_SCHOOL.tenant_id == 1000000000000000005
    assert DISABLED_SCHOOL.tenant_id == 1000000000000000006
    assert SANDBOX_SCHOOL.tenant_id == 1000000000000000007
    assert SANDBOX_SCHOOL.tenant_code == "sandbox-school"
    assert len({item.tenant_id for item in WELL_KNOWN_BY_CODE.values()}) == len(WELL_KNOWN_BY_CODE)
    assert tenant_context._MOCK_TENANTS["sandbox-school"]["tenantId"] == str(SANDBOX_SCHOOL.tenant_id)


def test_production_lookup_never_falls_back_to_mock_when_database_misses(monkeypatch):
    prod = SimpleNamespace(is_prod=True, DEFAULT_TENANT_CODE="sandbox-school")
    monkeypatch.setattr(tenant_context, "settings", prod)
    monkeypatch.setattr("app.db.session.db_enabled", lambda: True)
    monkeypatch.setattr(tenant_context, "_lookup_db_tenant", lambda code: None)
    assert tenant_context.lookup_tenant("sandbox-school") is None
    assert tenant_context.resolve_tenant(_request()) is None


def test_production_middleware_returns_503_when_default_tenant_truth_is_unavailable(monkeypatch):
    prod = SimpleNamespace(is_prod=True, DEFAULT_TENANT_CODE="sandbox-school")
    monkeypatch.setattr(tenant_context, "settings", prod)
    monkeypatch.setattr(context_middleware, "settings", prod)
    monkeypatch.setattr("app.db.session.db_enabled", lambda: True)
    monkeypatch.setattr(tenant_context, "_lookup_db_tenant", lambda code: None)

    middleware = context_middleware.RequestContextMiddleware(lambda scope, receive, send: None)

    async def forbidden_call_next(_request):
        raise AssertionError("production unresolved tenant must fail before routing")

    response = asyncio.run(middleware.dispatch(_request(), forbidden_call_next))
    assert response.status_code == 503
    assert b"TENANT_RESOLVER_UNAVAILABLE" in response.body


def test_browser_login_moves_refresh_token_to_httponly_cookie(monkeypatch):
    monkeypatch.setattr(
        auth_browser.auth_api,
        "login",
        lambda body: {
            "code": 0,
            "message": "ok",
            "data": {"accessToken": "access-visible", "refreshToken": "refresh-secret"},
        },
    )
    response = Response()
    payload = auth_browser.browser_login(
        auth_browser.auth_api.PasswordLoginRequest(loginName="student", password="secret"),
        response,
    )
    assert payload["data"] == {"accessToken": "access-visible"}
    cookie = response.headers.get("set-cookie", "").lower()
    assert "gx_refresh_v1=refresh-secret" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/api/v1/auth" in cookie


def test_browser_logout_terminates_cookie_session_without_live_access_token(monkeypatch):
    revoked = []
    monkeypatch.setattr(auth_browser, "consume_refresh", lambda token: {"userId": "db-student-1"})
    monkeypatch.setattr(auth_browser, "revoke_refresh_by_user", lambda user_id: revoked.append(user_id) or 1)
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: None)

    response = Response()
    payload = auth_browser.browser_logout(
        response=response,
        refresh_token="durable-cookie-token",
        authorization=None,
    )

    assert payload["code"] == 0
    assert payload["data"]["invalidated"] is True
    assert revoked == ["db-student-1"]
    cookie = response.headers.get("set-cookie", "").lower()
    assert "gx_refresh_v1=" in cookie
    assert "max-age=0" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie


def test_browser_logout_keeps_cookie_deletion_when_auth_store_fails(monkeypatch):
    def fail_consume(_token):
        raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503)

    monkeypatch.setattr(auth_browser, "consume_refresh", fail_consume)
    response = Response()
    payload = auth_browser.browser_logout(
        response=response,
        refresh_token="durable-cookie-token",
        authorization=None,
    )

    assert response.status_code == 503
    assert payload["bizCode"] == "AUTH_STORE_UNAVAILABLE"
    assert payload["code"] != 0
    cookie = response.headers.get("set-cookie", "").lower()
    assert "gx_refresh_v1=" in cookie
    assert "max-age=0" in cookie


def test_pc_browser_clients_do_not_persist_auth_tokens_in_web_storage():
    admin = (ROOT / "frontend/src/services/http/client.js").read_text(encoding="utf-8")
    portal = (ROOT / "student-portal/src/services/request.js").read_text(encoding="utf-8")
    portal_session = (ROOT / "student-portal/src/stores/session.js").read_text(encoding="utf-8")

    assert "sessionStorage.setItem" not in admin
    assert "localStorage.setItem" not in admin
    assert "state = { token: ''" in admin
    assert "/auth/browser-refresh" in admin
    assert "/auth/browser-login" in admin
    assert "await rawRequest('/auth/browser-logout', { method: 'POST', auth: false, forceProbe: true })" in admin
    assert "if (state.token) await rawRequest('/auth/browser-logout'" not in admin

    assert "localStorage.setItem" not in portal
    assert "_sessionSet(TOKEN_KEY" not in portal
    assert "_sessionSet(REFRESH_KEY" not in portal
    assert "let accessToken = ''" in portal
    assert "/auth/browser-refresh" in portal
    assert "/auth/browser-login" in portal
    assert "await request('/auth/browser-logout', { method: 'POST', auth: false })" in portal_session


def test_python_freeze_contract_is_self_consistent():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check/check-python-lock.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "python_lock_ok" in result.stdout
