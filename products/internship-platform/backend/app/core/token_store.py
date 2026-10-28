"""Standalone Redis-backed refresh-token and JTI store."""
from __future__ import annotations

import hashlib
import json
import math
import secrets
import time
from threading import RLock

from app.core.config import settings
from app.core.exceptions import AppException, unauthorized
from app.core.redis_client import _prefix, get_redis

REFRESH_TTL = max(1, int(getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7))) * 24 * 3600
AUTH_SESSION_PREFIX = 'auth-session:'
_memory_refresh: dict[str, dict] = {}
_memory_blocked: dict[str, float] = {}
# ponytail: process-local development fallback; Redis owns cross-process atomicity.
_memory_lock = RLock()


def _hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode()).hexdigest()


def _refresh_key(token: str) -> str:
    return _prefix(f"auth:refresh:{_hash(token)}")


def _client():
    client = get_redis()
    if client is None and (settings.is_prod or settings.REDIS_URL):
        raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503)
    if client is not None:
        try:
            policy = client.config_get('maxmemory-policy', 'appendonly', 'appendfsync')
            if (policy.get('maxmemory-policy') != 'noeviction'
                    or policy.get('appendonly') != 'yes' or policy.get('appendfsync') != 'always'):
                raise ValueError('revocation records require durable, non-evicting storage')
        except Exception as exc:
            raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储安全策略不可用，请联系管理员", http_status=503) from exc
    return client


def issue_refresh(claims: dict) -> str:
    session_id = str((claims or {}).get('authSessionId') or '').strip()
    if not session_id:
        raise unauthorized('会话缺少有效编号，请重新登录')
    token = secrets.token_urlsafe(48)
    payload = json.dumps(dict(claims or {}), ensure_ascii=False, separators=(",", ":"))
    client = _client()
    if client is not None:
        try:
            issued = client.eval("""
                if redis.call('EXISTS', KEYS[2]) == 1 then return 0 end
                redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
                return 1
            """, 2, _refresh_key(token), _prefix(f'auth:jti:{AUTH_SESSION_PREFIX}{session_id}'), payload, REFRESH_TTL)
        except Exception as exc:
            raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503) from exc
        if issued != 1:
            raise unauthorized('当前会话已退出，请重新登录')
        return token
    with _memory_lock:
        if _memory_blocked.get(AUTH_SESSION_PREFIX + session_id, 0) > time.time():
            raise unauthorized('当前会话已退出，请重新登录')
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
            if settings.is_prod or settings.REDIS_URL:
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
            if settings.is_prod or settings.REDIS_URL:
                raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503) from exc
            return None
    with _memory_lock:
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


def block_jti(jti: str, exp_ts: float | None = None, *, ttl_seconds: int | None = None) -> bool:
    value = str(jti or "").strip()
    if not value:
        return False
    exp = float(exp_ts or (time.time() + int(settings.JWT_EXPIRES_IN)))
    ttl = max(1, int(ttl_seconds)) if ttl_seconds is not None else max(1, math.ceil(exp - time.time()))
    client = _client()
    if client is not None:
        try:
            client.set(_prefix(f"auth:jti:{value}"), "1", ex=ttl)
            return True
        except Exception as exc:
            raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503) from exc
    with _memory_lock:
        _memory_blocked[value] = time.time() + ttl
    return not settings.is_prod


def jti_blocked(jti: str | None) -> bool:
    value = str(jti or "").strip()
    if not value:
        return False
    client = _client()
    if client is not None:
        try:
            return client.get(_prefix(f"auth:jti:{value}")) is not None
        except Exception as exc:
            raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503) from exc
    with _memory_lock:
        exp = _memory_blocked.get(value)
        if exp is None:
            return False
        if exp < time.time():
            _memory_blocked.pop(value, None)
            return False
        return True
