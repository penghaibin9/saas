"""Fail-soft, identity-isolated short cache for authenticated mobile read aggregations."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from app.core.context import current_tenant_id
from app.core.redis_client import cache_get_json, cache_set_json

_DEFAULT_TTL_SECONDS = 8


def mobile_read_cache_key(user: dict | None, endpoint: str) -> str:
    """Build a cache key that cannot be shared across tenants, users, roles or endpoints."""
    u = user or {}
    identity = {
        "tenantId": str(u.get("tenantId") or current_tenant_id() or "0"),
        "userType": str(u.get("userType") or ""),
        "roleCode": str(u.get("currentRoleCode") or ""),
        "userId": str(u.get("userId") or ""),
        "studentId": str(u.get("studentId") or ""),
        "loginName": str(u.get("loginName") or ""),
        "activeContextId": str(u.get("activeContextId") or ""),
        "endpoint": str(endpoint or "unknown"),
    }
    raw = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"mobile-read:v1:{endpoint}:{digest}"


def cached_mobile_read(
    user: dict | None,
    endpoint: str,
    loader: Callable[[], Any],
    *,
    ttl: int = _DEFAULT_TTL_SECONDS,
) -> Any:
    """Return a short cached read result; Redis failures safely fall through to the loader."""
    key = mobile_read_cache_key(user, endpoint)
    cached = cache_get_json(key)
    if isinstance(cached, dict):
        return cached

    value = loader()
    if isinstance(value, dict):
        cache_set_json(key, value, max(1, int(ttl)))
    return value
