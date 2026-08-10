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
