"""Persistent browser auth-session tombstones built on the existing JTI block store.

A browser session can have multiple short-lived access JTIs and can briefly have more than one
refresh row during a legitimate rotation race. Reusing the durable blocked-JTI store lets logout or
role switch invalidate the whole authSessionId without a schema migration.
"""
from __future__ import annotations

import math
import jwt

from app.core.token_store import AUTH_SESSION_PREFIX, REFRESH_TTL, block_jti, jti_blocked
from app.config import settings

def _key(session_id: str) -> str:
    return f"{AUTH_SESSION_PREFIX}{str(session_id or '').strip()}"


def block_auth_session(session_id: str) -> bool:
    session_id = str(session_id or "").strip()
    if not session_id:
        return False
    return block_jti(_key(session_id), ttl_seconds=max(REFRESH_TTL, int(settings.JWT_EXPIRES_IN)))


def auth_session_blocked(session_id: str | None) -> bool:
    session_id = str(session_id or "").strip()
    if not session_id:
        return False
    return jti_blocked(_key(session_id))


def _logout_access_claims(token: str) -> dict:
    """Verify expired access credentials only for revocation, never for authorization."""
    if not token or not settings.JWT_SECRET:
        return {}
    try:
        claims = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG],
                            options={"verify_exp": False, "require": ["exp", "jti"]})
        if not math.isfinite(float(claims['exp'])):
            return {}
        return claims
    except (jwt.InvalidTokenError, ValueError, TypeError):
        return {}


def revoke_logout_credentials(authorization: str | None, refresh_claims: dict | None = None) -> bool:
    raw = str(authorization or '').strip()
    token = raw.split(None, 1)[1].strip() if raw.lower().startswith('bearer ') else ''
    access = _logout_access_claims(token)
    if access.get('jti'):
        block_jti(access['jti'], float(access['exp']))
    session_ids = {str(claims.get('authSessionId') or '').strip()
                   for claims in (access, refresh_claims or {})}
    session_ids.discard('')
    for session_id in session_ids:
        block_auth_session(session_id)
    return bool(session_ids)
