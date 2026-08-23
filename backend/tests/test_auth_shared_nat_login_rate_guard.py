from __future__ import annotations

import pytest

from app.core.context import set_request_meta
from app.core.exceptions import AppException


def _load_runtime():
    import app.api.v1.router  # noqa: F401
    from app.api.v1 import auth as auth_api
    from app.services import control_plane_auth_service as p0

    return auth_api, p0


def test_password_login_paths_use_shared_nat_capacity_guard(monkeypatch):
    auth_api, p0 = _load_runtime()
    calls: list[tuple[str, int, int]] = []

    def allow(bucket: str, limit: int, window: int = 60) -> bool:
        calls.append((bucket, limit, window))
        return True

    monkeypatch.setattr(p0, "rate_limit", allow)

    set_request_meta({"ip": "10.88.0.10", "path": "/api/v1/auth/browser-login"})
    auth_api._login_rate_guard()
    set_request_meta({"ip": "10.88.0.10", "path": "/api/v1/auth/login"})
    p0.login_rate_guard()

    assert auth_api._login_rate_guard is p0.login_rate_guard
    assert calls == [
        ("login:10.88.0.10", 300, 60),
        ("login:10.88.0.10", 300, 60),
    ]
    set_request_meta(None)


def test_non_password_compat_login_keeps_legacy_ten_per_minute_cap(monkeypatch):
    auth_api, p0 = _load_runtime()
    calls: list[tuple[str, int, int]] = []

    def allow(bucket: str, limit: int, window: int = 60) -> bool:
        calls.append((bucket, limit, window))
        return True

    monkeypatch.setattr(p0, "rate_limit", allow)
    set_request_meta({"ip": "10.88.0.11", "path": "/api/v1/auth/wx-login"})

    auth_api._login_rate_guard()

    assert calls == [("login:10.88.0.11", 10, 60)]
    set_request_meta(None)


def test_shared_nat_guard_still_fails_closed_at_flood_cap(monkeypatch):
    auth_api, p0 = _load_runtime()
    monkeypatch.setattr(p0, "rate_limit", lambda *_args, **_kwargs: False)
    set_request_meta({"ip": "10.88.0.12", "path": "/api/v1/auth/browser-login"})

    with pytest.raises(AppException) as exc:
        auth_api._login_rate_guard()

    assert exc.value.code == "RATE_LIMITED"
    assert exc.value.http_status == 429
    set_request_meta(None)
