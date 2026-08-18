"""Platform recent-auth / external-or-native assurance policy."""
from __future__ import annotations

import time

from app.core.exceptions import AppException

MFA_AMR = frozenset({"mfa", "otp", "totp", "webauthn", "fido", "fido2", "hwk"})


def assurance_state(user: dict | None, *, max_age_seconds: int = 600) -> dict:
    user = user or {}
    raw_auth_time = user.get("authTime") or user.get("tokenIat")
    try:
        auth_time = int(raw_auth_time)
    except (TypeError, ValueError):
        auth_time = 0
    age = max(0, int(time.time()) - auth_time) if auth_time else None
    recent = bool(auth_time and age is not None and age <= int(max_age_seconds))
    amr = {str(value).strip().lower() for value in (user.get("amr") or []) if str(value).strip()}
    acr = str(user.get("acr") or "").strip().lower()
    mfa = bool(amr & MFA_AMR) or "mfa" in acr or "2fa" in acr or "multi" in acr
    return {
        "recent": recent,
        "ageSeconds": age,
        "maxAgeSeconds": int(max_age_seconds),
        "mfa": mfa,
        "amr": sorted(amr),
        "acr": user.get("acr"),
        "identityProvider": user.get("identityProvider"),
        "source": "SIGNED_TOKEN_CLAIMS",
    }


def assert_recent_platform_auth(user: dict | None, *, require_mfa: bool = False, max_age_seconds: int = 600) -> dict:
    state = assurance_state(user, max_age_seconds=max_age_seconds)
    if not state["recent"]:
        raise AppException(
            "PLATFORM_RECENT_AUTH_REQUIRED",
            "平台主管高危操作需要最近一次可信认证，请重新认证后重试",
            http_status=403,
            details={"maxAgeSeconds": int(max_age_seconds)},
        )
    if require_mfa and not state["mfa"]:
        raise AppException(
            "PLATFORM_MFA_ASSURANCE_REQUIRED",
            "该平台主管操作需要 MFA/二次认证保证；当前令牌未携带可信 ACR/AMR 证明",
            http_status=403,
        )
    return state
