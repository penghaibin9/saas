"""Explicit registry for domain-owned integrity probes."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.core.exceptions import AppException

WORKFLOW_CLOSED_TASK_PENDING = "WORKFLOW_CLOSED_TASK_PENDING"
COMPLETED_DOMAIN_TODO_PENDING = "COMPLETED_DOMAIN_TODO_PENDING"
REGISTERED_PROBE_CODES = frozenset({WORKFLOW_CLOSED_TASK_PENDING, COMPLETED_DOMAIN_TODO_PENDING})


@dataclass(frozen=True, slots=True)
class ProbeRequest:
    tenant_id: int
    after_id: int
    limit: int
    timeout_ms: int


Probe = Callable[[ProbeRequest], object]
_PROBES: dict[str, Probe] = {}


def register_integrity_probe(code: str):
    normalized = str(code or "").strip().upper()
    if normalized not in REGISTERED_PROBE_CODES:
        raise AppException("INTEGRITY_PROBE_NOT_ALLOWED", "探测器代码不在平台白名单", http_status=422)

    def decorator(function: Probe) -> Probe:
        if normalized in _PROBES and _PROBES[normalized] is not function:
            raise RuntimeError(f"integrity probe already registered: {normalized}")
        _PROBES[normalized] = function
        return function

    return decorator


def get_integrity_probe(code: str) -> Probe | None:
    return _PROBES.get(str(code or "").strip().upper())


def registered_probe_codes() -> tuple[str, ...]:
    return tuple(sorted(_PROBES))


__all__ = [
    "COMPLETED_DOMAIN_TODO_PENDING",
    "ProbeRequest",
    "REGISTERED_PROBE_CODES",
    "WORKFLOW_CLOSED_TASK_PENDING",
    "get_integrity_probe",
    "register_integrity_probe",
    "registered_probe_codes",
]
