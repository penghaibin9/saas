from __future__ import annotations

from types import SimpleNamespace

from app.api.v1 import auth_browser
from app.core import token_store
from app.services import browser_auth_session_service


def test_browser_sessionize_real_db_pair_keeps_one_session_id(monkeypatch):
    consumed = []
    access_claims = []
    refresh_claims = []

    monkeypatch.setattr(auth_browser, "decode_token", lambda token: {"userId": "db-7"})
    monkeypatch.setattr(
        auth_browser,
        "consume_refresh",
        lambda token: consumed.append(token) or {
            "userId": "db-7",
            "tenantId": "1001",
            "currentRoleCode": "COUNSELOR",
            "clientType": "PC",
        },
    )
    monkeypatch.setattr(
        auth_browser,
        "create_access_token",
        lambda claims: access_claims.append(dict(claims)) or "session-access",
    )
    monkeypatch.setattr(
        auth_browser,
        "issue_refresh",
        lambda claims: refresh_claims.append(dict(claims)) or "session-refresh",
    )

    payload = {
        "code": 0,
        "data": {"accessToken": "old-access", "refreshToken": "old-refresh", "userId": "db-7"},
    }
    result = auth_browser._sessionize_payload(payload)

    assert consumed == ["old-refresh"]
    assert result["data"]["accessToken"] == "session-access"
    assert result["data"]["refreshToken"] == "session-refresh"
    assert access_claims[0]["authSessionId"]
    assert access_claims[0]["authSessionId"] == refresh_claims[0]["authSessionId"]


def test_browser_sessionize_keeps_non_db_test_or_mock_pair_compatible(monkeypatch):
    monkeypatch.setattr(auth_browser, "decode_token", lambda token: {"userId": "fixture-user"})
    monkeypatch.setattr(
        auth_browser,
        "consume_refresh",
        lambda token: (_ for _ in ()).throw(AssertionError("mock pair must not be consumed")),
    )
    payload = {"code": 0, "data": {"accessToken": "stub-access", "refreshToken": "stub-refresh"}}
    assert auth_browser._sessionize_payload(payload) is payload


def test_browser_refresh_upgrades_legacy_cookie_to_session_scoped_pair(monkeypatch):
    access_claims = []
    refresh_claims = []
    monkeypatch.setattr(
        auth_browser,
        "consume_refresh",
        lambda token: {"userId": "db-7", "tenantId": "1001", "clientType": "PC"},
    )
    monkeypatch.setattr(auth_browser.auth_service_db, "validate_token_subject", lambda claims: claims)
    monkeypatch.setattr(
        auth_browser,
        "create_access_token",
        lambda claims: access_claims.append(dict(claims)) or "new-access",
    )
    monkeypatch.setattr(
        auth_browser,
        "issue_refresh",
        lambda claims: refresh_claims.append(dict(claims)) or "new-refresh",
    )
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: None)

    result = auth_browser._rotate_browser_refresh("legacy-cookie")
    assert result["data"]["accessToken"] == "new-access"
    assert result["data"]["refreshToken"] == "new-refresh"
    assert access_claims[0]["authSessionId"]
    assert access_claims[0]["authSessionId"] == refresh_claims[0]["authSessionId"]


class _FakeDb:
    def close(self):
        pass


def _stub_browser_switch(monkeypatch, *, session_id: str):
    target = {
        "contextId": "role:9",
        "roleCode": "INTERN_MENTOR",
        "roleName": "实习指导教师",
        "dataScope": "INTERN_STUDENTS",
    }
    user = SimpleNamespace(id=7)
    session_revokes = []
    global_revokes = []
    blocked = []

    monkeypatch.setattr(browser_auth_session_service, "get_sessionmaker", lambda: (lambda: _FakeDb()))
    monkeypatch.setattr(browser_auth_session_service.auth_service_db, "_load_token_user", lambda db, ctx: user)
    monkeypatch.setattr(browser_auth_session_service.auth_service_db, "_role_contexts", lambda db, u: [target])
    monkeypatch.setattr(
        browser_auth_session_service.auth_service_db,
        "_pick_context",
        lambda contexts, context_id=None: target if context_id == "role:9" else None,
    )
    monkeypatch.setattr(
        browser_auth_session_service.auth_service_db,
        "_login_result",
        lambda db, u, t, contexts, client_type: {"accessToken": "a", "refreshToken": "r"},
    )
    monkeypatch.setattr(
        browser_auth_session_service,
        "block_jti",
        lambda jti, exp: blocked.append((jti, exp)) or True,
    )
    monkeypatch.setattr(
        browser_auth_session_service,
        "revoke_refresh_by_session",
        lambda user_id, sid: session_revokes.append((user_id, sid)) or 1,
    )
    monkeypatch.setattr(
        browser_auth_session_service,
        "revoke_refresh_by_user",
        lambda user_id: global_revokes.append(user_id) or 1,
    )

    result = browser_auth_session_service.switch_role(
        {"userId": "db-7", "tokenJti": "old-jti", "tokenExp": 4102444800},
        "role:9",
        "PC",
        auth_session_id=session_id,
    )
    return result, blocked, session_revokes, global_revokes


def test_browser_role_switch_revokes_only_current_session(monkeypatch):
    result, blocked, session_revokes, global_revokes = _stub_browser_switch(monkeypatch, session_id="sess-1")
    assert blocked == [("old-jti", 4102444800)]
    assert session_revokes == [("db-7", "sess-1")]
    assert global_revokes == []
    assert result["contextType"] == "INTERN_MENTOR"


def test_browser_role_switch_legacy_access_fails_safe_once(monkeypatch):
    _result, _blocked, session_revokes, global_revokes = _stub_browser_switch(monkeypatch, session_id="")
    assert session_revokes == []
    assert global_revokes == ["db-7"]


def test_refresh_store_can_revoke_one_session_without_touching_sibling(monkeypatch):
    token_store.reset_all_for_tests()
    monkeypatch.setattr("app.db.session.db_enabled", lambda: False)
    token_store._refresh.update({
        "a1": {"claims": {"userId": "db-7", "authSessionId": "sess-a"}, "exp": token_store._now() + 60},
        "a2": {"claims": {"userId": "db-7", "authSessionId": "sess-a"}, "exp": token_store._now() + 60},
        "b1": {"claims": {"userId": "db-7", "authSessionId": "sess-b"}, "exp": token_store._now() + 60},
        "other": {"claims": {"userId": "db-8", "authSessionId": "sess-a"}, "exp": token_store._now() + 60},
    })
    try:
        assert token_store.revoke_refresh_by_session("db-7", "sess-a") == 2
        assert set(token_store._refresh) == {"b1", "other"}
    finally:
        token_store.reset_all_for_tests()
