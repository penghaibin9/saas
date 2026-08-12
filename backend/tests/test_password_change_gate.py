"""首次密码强制修改：服务端必须是授权真值，不能只靠前端跳转。"""
from __future__ import annotations

import pytest
from starlette.requests import Request

from app.core.exceptions import AppException
from app.core.security import create_access_token, get_current_user
from app.services.password_change_gate import is_password_change_allowlisted


def _request(path: str) -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 12345),
        "server": ("testserver", 443),
    })


def _token() -> str:
    return create_access_token({
        "userId": "db-123",
        "loginName": "first-login-user",
        "realName": "首次登录用户",
        "userType": "TEACHER",
        "tid": "school-a",
        "tenantId": "9",
        "activeContextId": "role:7",
        "currentRoleCode": "TEACHER",
        "permissionVersion": "u1|TEACHER:1",
    })


def _patch_authenticated_subject(monkeypatch, *, must_change: bool) -> None:
    from app.core import token_store
    from app.services import auth_service_db, password_change_gate

    monkeypatch.setattr(token_store, "jti_blocked", lambda _jti: False)
    monkeypatch.setattr(token_store, "rate_limit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(auth_service_db, "validate_token_subject", lambda user: user)
    monkeypatch.setattr(
        password_change_gate,
        "must_change_password_for_subject",
        lambda _user: must_change,
    )


def test_force_password_change_blocks_business_api_server_side(monkeypatch):
    _patch_authenticated_subject(monkeypatch, must_change=True)
    with pytest.raises(AppException) as exc:
        get_current_user(
            _request("/api/v1/students"),
            authorization=f"Bearer {_token()}",
        )
    assert exc.value.code == "PASSWORD_CHANGE_REQUIRED"
    assert exc.value.http_status == 403
    assert exc.value.details["path"] == "/api/v1/auth/change-password"


@pytest.mark.parametrize("path", [
    "/api/v1/auth/change-password",
    "/api/v1/auth/change-password/",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/api/v1/authz/logout",
    "/api/v1/authz/me",
])
def test_force_password_change_allows_only_recovery_paths(monkeypatch, path):
    _patch_authenticated_subject(monkeypatch, must_change=True)
    user = get_current_user(_request(path), authorization=f"Bearer {_token()}")
    assert user["userId"] == "db-123"


def test_normal_subject_is_not_restricted(monkeypatch):
    _patch_authenticated_subject(monkeypatch, must_change=False)
    user = get_current_user(
        _request("/api/v1/students"),
        authorization=f"Bearer {_token()}",
    )
    assert user["tenantId"] == "9"


def test_switch_role_is_not_in_password_change_allowlist():
    assert is_password_change_allowlisted("/api/v1/auth/change-password") is True
    assert is_password_change_allowlisted("/api/v1/auth/switch-role") is False
    assert is_password_change_allowlisted("/api/v1/auth/refresh") is False
    assert is_password_change_allowlisted("/api/v1/files/export") is False


def test_password_change_truth_cache_is_permission_version_scoped(monkeypatch):
    """安全事件后新版本 token 验真一次即恢复热路，同时保留旧无版本 token 阻断标记。"""
    from app.services import password_change_gate as gate

    store: dict[str, str] = {"auth:force-db:9:db-123": "1"}
    scalar_calls: list[object] = []
    deleted_keys: list[str] = []

    class FakeDb:
        def scalar(self, statement):
            scalar_calls.append(statement)
            return True

        def close(self):
            return None

    monkeypatch.setattr(gate, "db_enabled", lambda: True)
    monkeypatch.setattr(gate, "get_sessionmaker", lambda: (lambda: FakeDb()))
    monkeypatch.setattr(gate, "cache_get", lambda key: store.get(key))

    def fake_cache_set(key, value, _ttl):
        store[key] = value
        return True

    def fake_cache_delete(key):
        deleted_keys.append(key)
        store.pop(key, None)
        return 1

    monkeypatch.setattr(gate, "cache_set", fake_cache_set)
    monkeypatch.setattr(gate, "cache_delete", fake_cache_delete)

    subject = {"userId": "db-123", "tenantId": "9", "permissionVersion": "u1|TEACHER:1"}
    assert gate.must_change_password_for_subject(subject) is True
    assert gate.must_change_password_for_subject(subject) is True
    assert len(scalar_calls) == 1
    assert deleted_keys == ["auth:force-db:9:db-123"]
    assert "auth:force-db:9:db-123" not in store
    assert store["auth:block-versionless:9:db-123"] == "1"

    upgraded = {**subject, "permissionVersion": "u2|TEACHER:1"}
    assert gate.must_change_password_for_subject(upgraded) is True
    assert len(scalar_calls) == 2
    # force-db 已释放；普通新版本 cache miss 不再产生额外删除或重写 legacy block。
    assert deleted_keys == ["auth:force-db:9:db-123"]


@pytest.mark.parametrize("marker", [
    "auth:force-db:9:db-123",
    "auth:block-versionless:9:db-123",
])
def test_versionless_subject_is_blocked_after_password_security_event(monkeypatch, marker):
    """旧兼容 token 无 permissionVersion，密码重置后必须阻断业务而不能靠 DB 校验后继续使用。"""
    from app.services import password_change_gate as gate

    store = {marker: "1"}
    monkeypatch.setattr(gate, "db_enabled", lambda: True)
    monkeypatch.setattr(gate, "cache_get", lambda key: store.get(key))
    monkeypatch.setattr(gate, "get_sessionmaker", lambda: pytest.fail("blocked legacy token must not reach password truth DB"))

    subject = {"userId": "db-123", "tenantId": "9"}
    assert gate.must_change_password_for_subject(subject) is True


def test_password_change_truth_without_permission_version_never_uses_value_cache(monkeypatch):
    """没有安全事件时兼容旧 token 仍逐请求查库，不读写 permissionVersion 绑定的真值缓存。"""
    from app.services import password_change_gate as gate

    scalar_calls: list[object] = []

    class FakeDb:
        def scalar(self, statement):
            scalar_calls.append(statement)
            return False

        def close(self):
            return None

    monkeypatch.setattr(gate, "db_enabled", lambda: True)
    monkeypatch.setattr(gate, "get_sessionmaker", lambda: (lambda: FakeDb()))
    monkeypatch.setattr(gate, "cache_get", lambda _key: None)
    monkeypatch.setattr(gate, "cache_set", lambda *_args, **_kwargs: pytest.fail("versionless token must not write value cache"))
    monkeypatch.setattr(gate, "cache_delete", lambda *_args, **_kwargs: pytest.fail("versionless token must not clear force marker"))

    subject = {"userId": "db-123", "tenantId": "9"}
    assert gate.must_change_password_for_subject(subject) is False
    assert gate.must_change_password_for_subject(subject) is False
    assert len(scalar_calls) == 2
