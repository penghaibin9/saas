"""Fail-soft, identity-isolated short cache for authenticated mobile read aggregations."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from functools import wraps
from types import ModuleType
from typing import Any

from app.core.context import current_tenant_id
from app.core.redis_client import cache_get_json, cache_set_json

_DEFAULT_TTL_SECONDS = 8
_TARGETS = {
    "mobile_student_service": {
        "my_todos": "student-todos",
        "my_messages": "student-messages",
        "my_profile": "student-profile",
    },
    "mobile_teacher_service": {
        "overview": "teacher-overview",
        "todos": "teacher-todos",
        "risk_students": "teacher-risk-students",
        "my_classes": "teacher-my-classes",
    },
}


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


def install_mobile_read_wrappers(module_name: str, module: ModuleType) -> ModuleType:
    """Wrap only the approved authenticated read functions; safe to call repeatedly."""
    for function_name, endpoint in _TARGETS.get(module_name, {}).items():
        original = getattr(module, function_name)
        if getattr(original, "__mobile_read_cached__", False):
            continue

        @wraps(original)
        def wrapped(user, *args, __original=original, __endpoint=endpoint, **kwargs):
            return cached_mobile_read(
                user,
                __endpoint,
                lambda: __original(user, *args, **kwargs),
            )

        wrapped.__mobile_read_cached__ = True
        setattr(module, function_name, wrapped)
    return module
