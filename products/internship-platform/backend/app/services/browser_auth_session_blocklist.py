"""Persistent browser auth-session tombstones built on the existing JTI block store.

A browser session can have multiple short-lived access JTIs and can briefly have more than one
refresh row during a legitimate rotation race. Reusing the durable blocked-JTI store lets logout or
role switch invalidate the whole authSessionId without a schema migration.
"""
from __future__ import annotations

import time

from app.core.token_store import REFRESH_TTL, block_jti, jti_blocked

_PREFIX = "auth-session:"


def _key(session_id: str) -> str:
    return f"{_PREFIX}{str(session_id or '').strip()}"


def block_auth_session(session_id: str) -> bool:
    session_id = str(session_id or "").strip()
    if not session_id:
        return False
    return block_jti(_key(session_id), time.time() + REFRESH_TTL)


def auth_session_blocked(session_id: str | None) -> bool:
    session_id = str(session_id or "").strip()
    if not session_id:
        return False
    return jti_blocked(_key(session_id))
