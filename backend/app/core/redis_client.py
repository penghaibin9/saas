"""Optional Redis facade used by auth, rate limiting and short-lived caches.

The application remains runnable without Redis.  Every operation is fail-soft and
falls back to the existing database/in-memory path; failures are rate-limited in
logs and the client reconnects after a short cooldown.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from app.core.config import settings

log = logging.getLogger("app.redis")
_client = None
_retry_after = 0.0
_lock = threading.Lock()


def _prefix(key: str) -> str:
    env = (settings.APP_ENV or "dev").strip().lower()
    base = (settings.REDIS_KEY_PREFIX or "school-lifecycle").strip(":")
    return f"{base}:{env}:{key}"


def get_redis():
    """Return a live sync Redis client, or None while unavailable/unconfigured."""
    global _client, _retry_after
    if not (settings.REDIS_URL or "").strip():
        return None
    if _client is not None:
        return _client
    now = time.monotonic()
    if now < _retry_after:
        return None
    with _lock:
        if _client is not None:
            return _client
        if time.monotonic() < _retry_after:
            return None
        try:
            import redis
            candidate = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                health_check_interval=30,
                retry_on_timeout=True,
            )
            candidate.ping()
            _client = candidate
            return _client
        except Exception as exc:  # noqa: BLE001
            _retry_after = time.monotonic() + 5.0
            log.warning("redis unavailable; using safe fallback: %s", type(exc).__name__)
            return None


def reset_redis_client() -> None:
    """Close/reset the cached client (tests and graceful reconnects)."""
    global _client, _retry_after
    with _lock:
        old, _client, _retry_after = _client, None, 0.0
    if old is not None:
        try:
            old.close()
        except Exception:  # noqa: BLE001
            pass


def cache_get(key: str) -> str | None:
    client = get_redis()
    if client is None:
        return None
    try:
        return client.get(_prefix(key))
    except Exception as exc:  # noqa: BLE001
        _mark_failed(exc)
        return None


def cache_set(key: str, value: str, ttl: int) -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        client.set(_prefix(key), value, ex=max(1, int(ttl)))
        return True
    except Exception as exc:  # noqa: BLE001
        _mark_failed(exc)
        return False


def cache_delete(*keys: str) -> int:
    client = get_redis()
    if client is None or not keys:
        return 0
    try:
        return int(client.delete(*[_prefix(key) for key in keys]) or 0)
    except Exception as exc:  # noqa: BLE001
        _mark_failed(exc)
        return 0


def cache_delete_pattern(pattern: str, batch_size: int = 200) -> int:
    """Delete a bounded namespace pattern using SCAN (never blocking KEYS)."""
    client = get_redis()
    if client is None:
        return 0
    deleted = 0
    try:
        full_pattern = _prefix(pattern)
        batch: list[str] = []
        for key in client.scan_iter(match=full_pattern, count=max(10, batch_size)):
            batch.append(key)
            if len(batch) >= batch_size:
                deleted += int(client.delete(*batch) or 0)
                batch.clear()
        if batch:
            deleted += int(client.delete(*batch) or 0)
        return deleted
    except Exception as exc:  # noqa: BLE001
        _mark_failed(exc)
        return deleted


def cache_get_json(key: str) -> Any | None:
    raw = cache_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        cache_delete(key)
        return None


def cache_set_json(key: str, value: Any, ttl: int) -> bool:
    return cache_set(key, json.dumps(value, ensure_ascii=False, separators=(",", ":")), ttl)


def fixed_window_allow(bucket: str, limit: int, window: int) -> bool | None:
    """Distributed fixed-window limiter. None means Redis unavailable."""
    client = get_redis()
    if client is None:
        return None
    window = max(1, int(window))
    slot = int(time.time()) // window
    key = _prefix(f"rate:{bucket}:{slot}")
    try:
        pipe = client.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, window + 2)
        count, _ = pipe.execute()
        return int(count) <= max(1, int(limit))
    except Exception as exc:  # noqa: BLE001
        _mark_failed(exc)
        return None


def increment_with_ttl(key: str, ttl: int) -> int | None:
    """Atomically increment a shared counter and keep a bounded lifetime."""
    client = get_redis()
    if client is None:
        return None
    try:
        full_key = _prefix(key)
        pipe = client.pipeline(transaction=True)
        pipe.incr(full_key)
        pipe.expire(full_key, max(1, int(ttl)))
        count, _ = pipe.execute()
        return int(count)
    except Exception as exc:  # noqa: BLE001
        _mark_failed(exc)
        return None


def redis_health() -> dict:
    started = time.perf_counter()
    client = get_redis()
    if client is None:
        return {"ok": False, "configured": bool((settings.REDIS_URL or "").strip())}
    try:
        client.ping()
        return {"ok": True, "configured": True,
                "latencyMs": round((time.perf_counter() - started) * 1000, 2)}
    except Exception as exc:  # noqa: BLE001
        _mark_failed(exc)
        return {"ok": False, "configured": True, "error": type(exc).__name__}


def _mark_failed(exc: Exception) -> None:
    global _client, _retry_after
    log.warning("redis operation failed; using safe fallback: %s", type(exc).__name__)
    with _lock:
        old, _client, _retry_after = _client, None, time.monotonic() + 5.0
    if old is not None:
        try:
            old.close()
        except Exception:  # noqa: BLE001
            pass
