"""Authentication compatibility facade with signed assurance claims exposed to Platform PAM."""
from __future__ import annotations

from typing import Optional

from fastapi import Header, Request

from app.core import security_legacy as _legacy
from app.core.security_legacy import *  # noqa: F401,F403


def get_current_user(request: Request, authorization: Optional[str] = Header(default=None)) -> dict:
    """Preserve legacy authentication, then expose only server-verified JWT assurance claims."""
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
