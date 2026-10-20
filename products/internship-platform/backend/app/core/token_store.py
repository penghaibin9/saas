"""Standalone Redis-backed refresh-token and JTI store."""
from __future__ import annotations

import hashlib
import json
import secrets
import time

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.redis_client import _prefix, cache_get, get_redis

REFRESH_TTL = max(1, int(getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7))) * 24 * 3600
_memory_refresh: dict[str, dict] = {}
_memory_blocked: dict[str, float] = {}


def _hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode()).hexdigest()


def _refresh_key(token: str) -> str:
    return _prefix(f"auth:refresh:{_hash(token)}")


def _client():
    client = get_redis()
    if client is None and settings.is_prod:
        raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503)
    return client


def issue_refresh(claims: dict) -> str:
    token = secrets.token_urlsafe(48)
    payload = json.dumps(dict(claims or {}), ensure_ascii=False, separators=(",", ":"))
    client = _client()
    if client is not None:
        try:
            client.set(_refresh_key(token), payload, ex=REFRESH_TTL)
            return token
        except Exception as exc:
            if settings.is_prod:
                raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503) from exc
    _memory_refresh[token] = {"claims": dict(claims or {}), "exp": time.time() + REFRESH_TTL}
    return token


def _subject_matches(claims: dict, expected: dict) -> bool:
    keys = ("userId", "tenantId", "activeContextId", "clientType", "authSessionId")
    return all(str(claims.get(k) or "") == str(expected.get(k) or "") for k in keys)


def consume_refresh(token: str, *, expected_claims: dict | None = None) -> dict | None:
    client = _client()
    if client is not None:
        try:
            raw = client.getdel(_refresh_key(token))
            if not raw:
                return None
            claims = dict(json.loads(raw) or {})
            if expected_claims is not None and not _subject_matches(claims, expected_claims):
                return None
            return claims
        except Exception as exc:
            if settings.is_prod:
                raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503) from exc
            return None
    row = _memory_refresh.pop(str(token or ""), None)
    if not row or float(row.get("exp") or 0) < time.time():
        return None
    claims = dict(row.get("claims") or {})
    if expected_claims is not None and not _subject_matches(claims, expected_claims):
        return None
    return claims


def consume_refresh_if_matches(
    token: str,
    *,
    expected_browser_channel: str,
    expected_browser_session_hash: str,
) -> dict | None:
    channel = str(expected_browser_channel or "").strip().lower()
    session_hash = str(expected_browser_session_hash or "").strip()
    if not channel or not session_hash:
        return None
    client = _client()
    if client is not None:
        key = _refresh_key(token)
        try:
            with client.pipeline() as pipe:
                while True:
                    try:
                        pipe.watch(key)
                        raw = pipe.get(key)
                        if not raw:
                            pipe.unwatch()
                            return None
                        claims = dict(json.loads(raw) or {})
                        if (
                            str(claims.get("browserChannel") or "").strip().lower() != channel
                            or str(claims.get("browserSessionIdHash") or "") != session_hash
                        ):
                            pipe.unwatch()
                            return None
                        pipe.multi()
                        pipe.delete(key)
                        pipe.execute()
                        return claims
                    except Exception as watch_exc:
                        if watch_exc.__class__.__name__ == "WatchError":
                            continue
                        raise
        except Exception as exc:
            if settings.is_prod:
                raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503) from exc
            return None
    row = _memory_refresh.get(str(token or ""))
    if not row or float(row.get("exp") or 0) < time.time():
        _memory_refresh.pop(str(token or ""), None)
        return None
    claims = dict(row.get("claims") or {})
    if (
        str(claims.get("browserChannel") or "").strip().lower() != channel
        or str(claims.get("browserSessionIdHash") or "") != session_hash
    ):
        return None
    _memory_refresh.pop(str(token or ""), None)
    return claims


def block_jti(jti: str, exp_ts: float | None = None) -> bool:
    value = str(jti or "").strip()
    if not value:
        return False
    exp = float(exp_ts or (time.time() + int(settings.JWT_EXPIRES_IN)))
    ttl = max(1, int(exp - time.time()))
    client = _client()
    if client is not None:
        try:
            client.set(_prefix(f"auth:jti:{value}"), "1", ex=ttl)
            return True
        except Exception as exc:
            if settings.is_prod:
                raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503) from exc
    _memory_blocked[value] = exp
    return not settings.is_prod


def jti_blocked(jti: str | None) -> bool:
    value = str(jti or "").strip()
    if not value:
        return False
    if cache_get(f"auth:jti:{value}") == "1":
        return True
    exp = _memory_blocked.get(value)
    if exp is None:
        return False
    if exp < time.time():
        _memory_blocked.pop(value, None)
        return False
    return True
