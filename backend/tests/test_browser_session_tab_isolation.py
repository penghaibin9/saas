from __future__ import annotations

import inspect

import pytest

from fastapi import Response
from starlette.requests import Request

from app.api.v1 import auth_browser
from app.core import token_store
from app.core.exceptions import AppException


def _request(cookies: dict[str, str] | None = None) -> Request:
    raw = "; ".join(f"{k}={v}" for k, v in (cookies or {}).items()).encode()
    headers = [(b"cookie", raw)] if raw else []
    return Request({
        "type": "http", "http_version": "1.1", "method": "POST", "scheme": "https",
        "path": "/api/v1/auth/browser-refresh", "raw_path": b"/api/v1/auth/browser-refresh",
        "query_string": b"", "headers": headers, "client": ("127.0.0.1", 12345),
        "server": ("example.test", 443),
    })


def test_browser_login_sets_session_specific_cookie_slot(monkeypatch):
    monkeypatch.setattr(auth_browser.auth_api, "login", lambda body: {
        "code": 0, "message": "ok", "data": {"accessToken": "access", "refreshToken": "refresh-a"},
    })
    monkeypatch.setattr(auth_browser, "_sessionize_payload", lambda payload, **kwargs: payload)
    monkeypatch.setattr(auth_browser, "_channel_from_access_token", lambda token: "staff")
    response = Response()
    auth_browser.browser_login(
        auth_browser.auth_api.PasswordLoginRequest(loginName="teacher", password="secret", clientType="PC"),
        response, "tab-a",
    )
    cookies = "\n".join(response.headers.getlist("set-cookie"))
    assert f"{auth_browser._cookie_name('staff', 'tab-a')}=refresh-a" in cookies
    assert auth_browser._cookie_name("staff", "tab-b") not in cookies


def test_browser_refresh_rejects_missing_session_id():
    try:
        auth_browser.browser_refresh(_request(), Response(), browser_session="staff", browser_session_id=None)
    except AppException as exc:
        assert exc.http_status == 401
    else:
        raise AssertionError("missing X-Browser-Session-Id must fail")


def test_browser_refresh_rejects_other_session_cookie_without_consuming_it(monkeypatch):
    called = []
    monkeypatch.setattr(auth_browser, "consume_refresh_if_matches", lambda *args, **kwargs: called.append(1) or None)
    cookies = {auth_browser._cookie_name("staff", "tab-b"): "refresh-b"}
    try:
        auth_browser.browser_refresh(_request(cookies), Response(), browser_session="staff", browser_session_id="tab-a")
    except AppException as exc:
        assert exc.http_status == 401
    else:
        raise AssertionError("other tab cookie must fail")
    assert called == []


def test_atomic_match_mismatch_does_not_burn_refresh_token():
    token_store._refresh.clear()
    claims = {"userId": "db-1", "browserChannel": "staff", "browserSessionIdHash": "hash-a"}
    token = token_store.issue_refresh(dict(claims))
    assert token_store.consume_refresh_if_matches(
        token, expected_browser_channel="staff", expected_browser_session_hash="hash-b",
    ) is None
    assert token in token_store._refresh
    assert token_store.consume_refresh_if_matches(
        token, expected_browser_channel="staff", expected_browser_session_hash="hash-a",
    ) == claims
    assert token not in token_store._refresh


def test_browser_logout_consumes_only_current_session_refresh(monkeypatch):
    token_store._refresh.clear()
    sid_a, sid_b = "tab-a", "tab-b"
    token_a = token_store.issue_refresh({
        "userId": "db-1", "authSessionId": "auth-a", "browserChannel": "staff",
        "browserSessionIdHash": auth_browser._browser_session_hash(sid_a),
    })
    token_b = token_store.issue_refresh({
        "userId": "db-1", "authSessionId": "auth-b", "browserChannel": "staff",
        "browserSessionIdHash": auth_browser._browser_session_hash(sid_b),
    })
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_browser, "block_auth_session", lambda *args, **kwargs: None)
    result = auth_browser._browser_logout(
        response=Response(), channel="staff", browser_session_id=sid_a,
        refresh_token=token_a, authorization=None,
    )
    assert result["code"] == 0
    assert token_a not in token_store._refresh and token_b in token_store._refresh
    assert token_store.consume_refresh_if_matches(
        token_b, expected_browser_channel="staff",
        expected_browser_session_hash=auth_browser._browser_session_hash(sid_b),
    ) is not None


def test_browser_logout_does_not_revoke_other_same_user_session():
    assert not hasattr(auth_browser, "_BROWSER_REVOKE_SESSION")
    assert "revoke_refresh_by_user" not in auth_browser._browser_logout.__code__.co_names


@pytest.mark.parametrize("bound_channel,bound_tab", [("student", "tab-a"), ("staff", "tab-b")])
def test_browser_logout_binding_mismatch_keeps_real_refresh_token(monkeypatch, bound_channel, bound_tab):
    token_store._refresh.clear()
    token = token_store.issue_refresh({
        "userId": "db-1", "authSessionId": "other-session", "browserChannel": bound_channel,
        "browserSessionIdHash": auth_browser._browser_session_hash(bound_tab),
    })
    monkeypatch.setattr(auth_browser, "block_auth_session", lambda *args: pytest.fail("unmatched session must remain valid"))
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: pytest.fail("unmatched logout must not succeed"))
    response = Response()
    result = auth_browser.browser_logout(
        _request({auth_browser._cookie_name("staff", "tab-a"): token}), response,
        browser_session="staff", browser_session_id="tab-a", authorization=None,
    )
    assert response.status_code == 401 and result["code"] != 0
    assert token in token_store._refresh
    assert token_store.consume_refresh_if_matches(
        token, expected_browser_channel=bound_channel,
        expected_browser_session_hash=auth_browser._browser_session_hash(bound_tab),
    ) is not None


@pytest.mark.parametrize("refresh_session,access_session,expected", [
    ("auth-a", "auth-a", ["auth-a"]),
    ("auth-a", "auth-b", ["auth-a", "auth-b"]),
    (None, "auth-a", ["auth-a"]),
    ("auth-a", None, ["auth-a"]),
])
def test_browser_logout_persists_each_bound_session_once_and_still_blocks_access_jti(
    monkeypatch, refresh_session, access_session, expected,
):
    sessions, access_jtis, audits = [], [], []
    binding = {"userId": "db-1", "browserChannel": "staff",
               "browserSessionIdHash": auth_browser._browser_session_hash("tab-a")}
    monkeypatch.setattr(auth_browser, "consume_refresh_if_matches", lambda token, **kwargs:
                        {**binding, "authSessionId": refresh_session})
    monkeypatch.setattr(auth_browser, "decode_token", lambda token:
                        {**binding, "authSessionId": access_session, "jti": "access-a", "exp": 2000000000})

    def persist_session(session_id):
        if session_id in sessions:
            raise AppException("AUTH_STORE_UNAVAILABLE", "duplicate session tombstone", http_status=503)
        sessions.append(session_id)
        return True

    monkeypatch.setattr(auth_browser, "block_auth_session", persist_session)
    monkeypatch.setattr(auth_browser, "block_jti", lambda jti, exp: access_jtis.append((jti, exp)) or True)
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: audits.append(kwargs))
    response = Response()
    result = auth_browser._browser_logout(response=response, channel="staff", browser_session_id="tab-a",
        refresh_token="refresh-a" if refresh_session else None,
        authorization="Bearer access-a" if access_session else None)
    assert response.status_code == 200 and result["code"] == 0
    assert sessions == expected
    assert access_jtis == ([("access-a", 2000000000.0)] if access_session else [])
    assert len(audits) == 1


def test_browser_logout_keeps_real_persistence_failure_as_failure(monkeypatch):
    monkeypatch.setattr(auth_browser, "consume_refresh_if_matches", lambda *args, **kwargs:
                        {"userId": "db-1", "authSessionId": "auth-a"})
    def unavailable(session_id):
        raise AppException("AUTH_STORE_UNAVAILABLE", "storage failure", http_status=503)
    monkeypatch.setattr(auth_browser, "block_auth_session", unavailable)
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs:
                        pytest.fail("failed logout must not record successful revocation"))
    response = Response()
    result = auth_browser._browser_logout(response=response, channel="staff", browser_session_id="tab-a",
        refresh_token="refresh-a", authorization=None)
    assert response.status_code == 503 and result["bizCode"] == "AUTH_STORE_UNAVAILABLE"


def test_browser_logout_still_rejects_access_from_another_tab(monkeypatch):
    sessions, access_jtis = [], []
    monkeypatch.setattr(auth_browser, "consume_refresh_if_matches", lambda *args, **kwargs:
                        {"userId": "db-1", "authSessionId": "auth-a"})
    monkeypatch.setattr(auth_browser, "decode_token", lambda token:
                        {"userId": "db-1", "authSessionId": "auth-b", "jti": "other-access",
                         "browserChannel": "staff", "browserSessionIdHash": auth_browser._browser_session_hash("tab-b")})
    monkeypatch.setattr(auth_browser, "block_auth_session", lambda sid: sessions.append(sid) or True)
    monkeypatch.setattr(auth_browser, "block_jti", lambda *args: access_jtis.append(args))
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs:
                        pytest.fail("unmatched access must not record successful logout"))
    response = Response()
    result = auth_browser._browser_logout(response=response, channel="staff", browser_session_id="tab-a",
        refresh_token="refresh-a", authorization="Bearer other-access")
    assert response.status_code == 401 and result["code"] != 0
    assert sessions == ["auth-a"] and access_jtis == []


def test_browser_switch_role_rotates_only_current_session_slot(monkeypatch):
    sid = "tab-a"
    monkeypatch.setattr(auth_browser, "decode_token", lambda token: {
        "userId": "db-1", "authSessionId": "old-auth-session", "browserChannel": "staff",
        "browserSessionIdHash": auth_browser._browser_session_hash(sid),
    })
    monkeypatch.setattr(auth_browser.browser_auth_session_service, "switch_role", lambda *args, **kwargs: {
        "accessToken": "new-access", "refreshToken": "new-refresh",
    })
    monkeypatch.setattr(auth_browser, "_sessionize_payload", lambda payload, **kwargs: payload)
    monkeypatch.setattr(auth_browser, "_channel_from_access_token", lambda token: "staff")
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: None)
    response = Response()
    result = auth_browser.browser_switch_role(
        auth_browser.SwitchRoleRequest(contextId="ctx-2", clientType="PC"), response,
        user={"userId": "db-1"}, authorization="Bearer old-access",
        browser_session="staff", browser_session_id=sid,
    )
    assert result["code"] == 0
    cookies = "\n".join(response.headers.getlist("set-cookie"))
    assert f"{auth_browser._cookie_name('staff', sid)}=new-refresh" in cookies
    assert auth_browser._cookie_name("staff", "tab-b") not in cookies


def test_staff_student_platform_slots_remain_isolated():
    sid = "same-tab-label"
    assert len({
        auth_browser._cookie_name("staff", sid),
        auth_browser._cookie_name("student", sid),
        auth_browser._cookie_name("platform", sid),
    }) == 3


def test_token_store_db_match_uses_row_lock_before_delete():
    source = inspect.getsource(token_store.consume_refresh_if_matches)
    assert ".with_for_update()" in source
    assert source.index("browserSessionIdHash") < source.index("delete(AuthRefreshToken)")
