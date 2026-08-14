"""Canonical audit facade with Control Plane critical-action extensions."""
from __future__ import annotations

from app.services import audit_log_legacy as _legacy

_legacy.CRITICAL_ACTIONS = frozenset(set(_legacy.CRITICAL_ACTIONS) | {
    "SECURITY_CHANGE_ACTIVATE",
    "SECURITY_CHANGE_ROLLBACK",
    "PLATFORM_DUTY_CHANGE",
    "PLATFORM_ELEVATION_CHANGE",
    "PLATFORM_SUPPORT_SESSION_CHANGE",
})

from app.services.audit_log_legacy import *  # noqa: F401,F403,E402

CRITICAL_ACTIONS = _legacy.CRITICAL_ACTIONS


def __getattr__(name: str):
    return getattr(_legacy, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy)))
