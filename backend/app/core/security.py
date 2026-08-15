"""Authentication compatibility facade with signed assurance claims exposed to Platform PAM.

The legacy module remains the frozen authentication implementation, but this
facade is the public Control Plane import surface.  Keep one mutable settings
reference at that surface and explicitly synchronize it before calls whose
production-safety decision depends on configuration.  This avoids a facade
monkeypatch/config reload mutating ``security.settings`` while legacy guards
silently keep reading a stale object.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Header, Request

from app.core import security_legacy as _legacy
from app.core.security_legacy import *  # noqa: F401,F403

# Public configuration authority for callers importing app.core.security.
# In normal runtime this is the same object as security_legacy.settings; tests,
# startup reloads or controlled overrides may replace this facade reference.
settings = _legacy.settings


def _sync_legacy_settings() -> None:
    """Keep frozen legacy functions on the facade's current settings object."""
    if _legacy.settings is not settings:
        _legacy.settings = settings


def assert_secret_safe() -> None:
    _sync_legacy_settings()
    return _legacy.assert_secret_safe()


def assert_prod_flags_safe() -> None:
    _sync_legacy_settings()
    return _legacy.assert_prod_flags_safe()


def assert_cors_safe() -> None:
    _sync_legacy_settings()
    return _legacy.assert_cors_safe()


def assert_scale_safe() -> None:
    _sync_legacy_settings()
    return _legacy.assert_scale_safe()


def assert_scheduler_safe() -> None:
    _sync_legacy_settings()
    return _legacy.assert_scheduler_safe()


def create_access_token(payload: dict, *, expires_in: int | None = None) -> str:
    _sync_legacy_settings()
    return _legacy.create_access_token(payload, expires_in=expires_in)


def decode_token(token: str) -> dict:
    _sync_legacy_settings()
    return _legacy.decode_token(token)


def get_current_user(request: Request, authorization: Optional[str] = Header(default=None)) -> dict:
    """Preserve legacy authentication, then expose only server-verified JWT assurance claims."""
    _sync_legacy_settings()
    user = _legacy.get_current_user(request, authorization)
    token = _legacy._extract_bearer(authorization)
    if not token:
        return user
    claims = _legacy.decode_token(token)
    user["tokenIat"] = claims.get("iat")
    user["authTime"] = claims.get("auth_time") or claims.get("authTime") or claims.get("iat")
    raw_amr = claims.get("amr") or []
    user["amr"] = list(raw_amr) if isinstance(raw_amr, (list, tuple, set)) else [str(raw_amr)] if raw_amr else []
    user["acr"] = claims.get("acr")
    user["identityProvider"] = claims.get("idp") or claims.get("iss")
    return user


def __getattr__(name: str):
    return getattr(_legacy, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy)))