"""Redis-backed idempotency records for expensive or write-sensitive endpoints."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.redis_client import cache_get_json, cache_set_json, cache_set_json_if_absent

TTL_SECONDS = 15 * 60


def _fingerprint(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def begin(user: dict, operation: str, key: str | None, payload: Any) -> tuple[Any | None, tuple[str, str] | None]:
    """Return a cached result or an opaque handle to save a new result.

    Redis unavailability is fail-soft: callers still execute, while their own
    database state checks remain the final duplicate-write guard.
    """
    raw_key = (key or "").strip()
    if not raw_key:
        return None, None
    if len(raw_key) < 8 or len(raw_key) > 128:
        raise AppException("VALIDATION_ERROR", "Idempotency-Key 长度必须为 8 到 128 个字符")
    tenant_id = str(current_tenant_id() or user.get("tenantId") or "-")
    user_id = str(user.get("userId") or "-")
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    cache_key = f"idempotency:{tenant_id}:{user_id}:{operation}:{key_hash}"
    fingerprint = _fingerprint(payload)
    cached = cache_get_json(cache_key)
    if isinstance(cached, dict):
        if cached.get("fingerprint") != fingerprint:
            raise AppException("DATA_CONFLICT", "同一个 Idempotency-Key 不能用于不同请求内容")
        if cached.get("state") == "PROCESSING":
            raise AppException("DATA_CONFLICT", "相同请求正在处理中，请勿重复提交")
        return cached.get("result"), None

    reservation = {"fingerprint": fingerprint, "state": "PROCESSING"}
    acquired = cache_set_json_if_absent(cache_key, reservation, TTL_SECONDS)
    if acquired is False:
        cached = cache_get_json(cache_key)
        if isinstance(cached, dict) and cached.get("fingerprint") != fingerprint:
            raise AppException("DATA_CONFLICT", "同一个 Idempotency-Key 不能用于不同请求内容")
        if isinstance(cached, dict) and cached.get("state") != "PROCESSING":
            return cached.get("result"), None
        raise AppException("DATA_CONFLICT", "相同请求正在处理中，请勿重复提交")
    return None, (cache_key, fingerprint)


def finish(handle: tuple[str, str] | None, result: Any, ttl: int = TTL_SECONDS) -> None:
    if handle is None:
        return
    cache_key, fingerprint = handle
    cache_set_json(cache_key, {"fingerprint": fingerprint, "state": "DONE", "result": result}, ttl)
