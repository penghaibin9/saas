"""Teacher Miniapp V3 T10 anonymous observability helpers.

This module is deliberately teacher-only and additive so Final Gold instrumentation does not
change shared Student V3 authorities. Labels are fixed route/scope tokens; callers must never
pass names, student numbers, message content, SQL, or object ids.
"""
from __future__ import annotations

from time import perf_counter

from app.services import mobile_observability_service as mobile_obs

_ALLOWED_ROUTES = {
    "teacher_my_students",
    "teacher_messages",
    "teacher_messages_badges",
}
_ALLOWED_SCOPES = {
    "ADMIN_TENANT",
    "SCOPED",
    "DENY",
    "MESSAGE_CONTEXT",
    "MESSAGE_GLOBAL",
    "UNKNOWN",
    "ERROR",
}


def _route(value: str) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in _ALLOWED_ROUTES else "unknown"


def _scope(value: str | None) -> str:
    normalized = str(value or "UNKNOWN").strip().upper()
    return normalized if normalized in _ALLOWED_SCOPES else "UNKNOWN"


def record_page_read(*, route_key: str, scope_mode: str | None, started: float) -> None:
    """Record latency bucket + anonymous scope label for one completed/failed read."""
    elapsed_ms = max(0.0, (perf_counter() - float(started)) * 1000.0)
    route = _route(route_key)
    scope = _scope(scope_mode)
    mobile_obs.record_latency("pageLatency", elapsed_ms)
    mobile_obs.record("scopeMode", f"{route}:{scope}")
