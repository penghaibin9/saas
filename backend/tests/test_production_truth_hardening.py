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
from app.core import security, tenant_context
from app.core.context import get_tenant
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


def test_signed_old_sandbox_token_cannot_bind_trial_tenant_after_identity_correction(monkeypatch):
    monkeypatch.setattr(
        security,
        "decode_token",
        lambda token: {
            "userId": "db-42",
            "userType": "STUDENT",
            "tid": SANDBOX_SCHOOL.tenant_code,
            "tenantId": str(TRIAL_SCHOOL.tenant_id),
        },
    )
    request = _request(headers=[(b"authorization", b"Bearer old-but-signed-token")])
    resolved = {
        "tenantId": str(SANDBOX_SCHOOL.tenant_id),
        "tenantCode": SANDBOX_SCHOOL.tenant_code,
        "tenantName": "体验沙箱学校",
        "status": "ACTIVE",
    }
    denied = context_middleware._token_tenant_identity_deny(request, resolved)
    assert denied is not None
    assert denied.status_code == 401
    assert b"TOKEN_TENANT_MISMATCH" in denied.body


def test_matching_signed_school_identity_passes_middleware_tenant_guard(monkeypatch):
    monkeypatch.setattr(
        security,
        "decode_token",
        lambda token: {
            "userId": "db-42",
            "userType": "STUDENT",
            "tid": SANDBOX_SCHOOL.tenant_code,
            "tenantId": str(SANDBOX_SCHOOL.tenant_id),
        },
    )
    request = _request(headers=[(b"authorization", b"Bearer current-signed-token")])
    resolved = {
        "tenantId": str(SANDBOX_SCHOOL.tenant_id),
        "tenantCode": SANDBOX_SCHOOL.tenant_code,
        "tenantName": "体验沙箱学校",
        "status": "ACTIVE",
    }
    assert context_middleware._token_tenant_identity_deny(request, resolved) is None


def test_staging_enforces_tenant_identity_even_for_non_db_subject(monkeypatch):
    staging = SimpleNamespace(is_prod=False, APP_ENV="staging")
    monkeypatch.setattr(context_middleware, "settings", staging)
    monkeypatch.setattr(
        security,
        "decode_token",
        lambda token: {
            "userId": "fixture-user",
            "userType": "STUDENT",
            "tid": SANDBOX_SCHOOL.tenant_code,
            "tenantId": str(TRIAL_SCHOOL.tenant_id),
        },
    )
    request = _request(headers=[(b"authorization", b"Bearer staging-token")])
    resolved = {
        "tenantId": str(SANDBOX_SCHOOL.tenant_id),
        "tenantCode": SANDBOX_SCHOOL.tenant_code,
        "tenantName": "体验沙箱学校",
        "status": "ACTIVE",
    }
    denied = context_middleware._token_tenant_identity_deny(request, resolved)
    assert denied is not None
    assert denied.status_code == 401


def test_test_only_synthetic_token_keeps_fixture_local_numeric_tenant(monkeypatch):
    test_settings = SimpleNamespace(is_prod=False, APP_ENV="test")
    monkeypatch.setattr(context_middleware, "settings", test_settings)
    monkeypatch.setattr(
        security,
        "decode_token",
        lambda token: {
            "userId": "fixture-user",
            "userType": "STUDENT",
            "tid": SANDBOX_SCHOOL.tenant_code,
            "tenantId": str(TRIAL_SCHOOL.tenant_id),
        },
    )
    resolved = {
        "tenantId": str(SANDBOX_SCHOOL.tenant_id),
        "tenantCode": SANDBOX_SCHOOL.tenant_code,
        "tenantName": "体验沙箱学校",
        "status": "ACTIVE",
    }
    monkeypatch.setattr(tenant_context, "lookup_tenant", lambda code: resolved)
    request = _request(headers=[(b"authorization", b"Bearer synthetic-test-token")])
    assert context_middleware._token_tenant_identity_deny(request, resolved) is None
    context_middleware._bind_token_tenant(request)
    assert get_tenant()["tenantId"] == str(TRIAL_SCHOOL.tenant_id)


def test_browser_session_cookie_names_are_isolated_per_pc_surface():
    assert auth_browser._COOKIE_PREFIXES == {
        "staff": "gx_staff_refresh_v2_",
        "platform": "gx_platform_refresh_v2_",
        "student": "gx_student_refresh_v2_",
    }
    assert len(set(auth_browser._COOKIE_PREFIXES.values())) == 3
    assert auth_browser._cookie_name("staff", "tab-a") != auth_browser._cookie_name("staff", "tab-b")


def test_browser_login_moves_refresh_token_to_tab_specific_httponly_cookie(monkeypatch):
    monkeypatch.setattr(auth_browser.auth_api, "login", lambda body: {
        "code": 0, "message": "ok",
        "data": {"accessToken": "access-visible", "refreshToken": "refresh-secret"},
    })
    monkeypatch.setattr(auth_browser, "_sessionize_payload", lambda payload, **kwargs: payload)
    monkeypatch.setattr(auth_browser, "_channel_from_access_token", lambda token: "student")
    response = Response()
    payload = auth_browser.browser_login(
        auth_browser.auth_api.PasswordLoginRequest(loginName="student", password="secret", clientType="STUDENT_PC"),
        response, "tab-student-a",
    )
    assert payload["data"] == {"accessToken": "access-visible"}
    cookies = "\n".join(response.headers.getlist("set-cookie")).lower()
    expected = auth_browser._cookie_name("student", "tab-student-a").lower()
    assert f"{expected}=refresh-secret" in cookies
    assert "gx_student_refresh_v1=refresh-secret" not in cookies
    assert "httponly" in cookies and "samesite=strict" in cookies and "path=/api/v1/auth" in cookies


def test_browser_logout_terminates_only_current_bound_refresh(monkeypatch):
    blocked = []
    monkeypatch.setattr(auth_browser, "consume_refresh_if_matches", lambda token, **kwargs: {
        "userId": "db-student-1", "authSessionId": "auth-session-a",
        "browserChannel": "student", "browserSessionIdHash": auth_browser._browser_session_hash("tab-a"),
    })
    monkeypatch.setattr(auth_browser, "block_auth_session", blocked.append)
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: None)
    response = Response()
    payload = auth_browser._browser_logout(
        response=response, channel="student", browser_session_id="tab-a",
        refresh_token="durable-cookie-token", authorization=None,
    )
    assert payload["code"] == 0 and payload["data"]["invalidated"] is True
    assert blocked == ["auth-session-a"]
    cookies = "\n".join(response.headers.getlist("set-cookie")).lower()
    assert auth_browser._cookie_name("student", "tab-a").lower() in cookies
    assert "max-age=0" in cookies


def test_browser_logout_blacklists_live_access_jti_for_same_tab(monkeypatch):
    blocked_jti, blocked_sessions = [], []
    sid = "tab-a"
    monkeypatch.setattr(auth_browser, "decode_token", lambda token: {
        "userId": "db-student-1", "jti": "access-jti-1", "exp": 4102444800,
        "authSessionId": "auth-session-a", "browserChannel": "student",
        "browserSessionIdHash": auth_browser._browser_session_hash(sid),
    })
    monkeypatch.setattr(auth_browser, "block_jti", lambda jti, exp: blocked_jti.append((jti, exp)) or True)
    monkeypatch.setattr(auth_browser, "block_auth_session", blocked_sessions.append)
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: None)
    payload = auth_browser._browser_logout(
        response=Response(), channel="student", browser_session_id=sid,
        refresh_token=None, authorization="Bearer live-access-token",
    )
    assert payload["code"] == 0
    assert blocked_jti == [("access-jti-1", 4102444800.0)]
    assert blocked_sessions == ["auth-session-a"]


def test_pc_browser_clients_persist_only_nonsecret_per_tab_session_id():
    admin = (ROOT / "frontend/src/services/http/client.js").read_text(encoding="utf-8")
    portal = (ROOT / "student-portal/src/services/request.js").read_text(encoding="utf-8")
    portal_session = (ROOT / "student-portal/src/stores/session.js").read_text(encoding="utf-8")
    assert "const BROWSER_SESSION_ID_KEY = 'gx_browser_session_id_v2'" in admin
    assert "sessionStorage.setItem(BROWSER_SESSION_ID_KEY" in admin
    assert "'X-Browser-Session-Id': getOrCreateBrowserSessionId()" in admin
    assert "state.refreshToken" not in admin
    assert "_sessionSet(TOKEN_KEY" not in portal and "_sessionSet(REFRESH_KEY" not in portal
    assert "const BROWSER_SESSION_ID_KEY = 'gx_browser_session_id_v2'" in portal
    assert "sessionStorage.setItem(BROWSER_SESSION_ID_KEY" in portal
    assert "'X-Browser-Session-Id': getOrCreateBrowserSessionId()" in portal
    assert "let accessToken = ''" in portal and "clientType: 'STUDENT_PC'" in portal
    assert "/auth/browser-refresh" in portal and "/auth/browser-login" in portal
    assert "await request('/auth/browser-logout', { method: 'POST', auth: true })" in portal_session


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
