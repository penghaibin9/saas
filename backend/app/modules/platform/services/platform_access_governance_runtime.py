"""B2 stabilization: replay-safe Platform PAM commands.

The canonical B2 service owns validation and atomic writes. This adapter adds a
stable requestId replay check before commands that add server-generated time or
snapshot fields, so a network retry returns the original grant instead of
conflicting on a digest that naturally changes over time.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.platform.services import platform_access_governance_service as _base


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _existing(config_type: str, tenant_id: int, key: str):
    from app.models import PlatformConfig

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == int(tenant_id),
            PlatformConfig.config_type == config_type,
            PlatformConfig.config_key == key,
            PlatformConfig.is_deleted.is_(False),
        )).first()
        return _base._row_to_dict(row) if row is not None else None
    finally:
        db.close()


def _same_or_conflict(existing: dict | None, expected: dict, *, fields: tuple[str, ...]) -> dict | None:
    if existing is None:
        return None
    mismatches = []
    for field in fields:
        left = existing.get(field)
        right = expected.get(field)
        if isinstance(left, list) or isinstance(right, list):
            left = sorted(left or [])
            right = sorted(right or [])
        if _stable(left) != _stable(right):
            mismatches.append(field)
    if mismatches:
        raise AppException(
            "IDEMPOTENCY_CONFLICT",
            "相同 requestId 已用于不同的平台访问请求",
            http_status=409,
            details={"mismatchedFields": mismatches},
        )
    return existing


def create_elevation(payload: dict, *, actor: dict | None = None) -> dict:
    key = _base._idempotent_key("elev", payload.get("requestId"))
    expected = {
        "requestId": payload.get("requestId"),
        "userId": str(payload.get("userId") or "").strip(),
        "durationMinutes": int(payload.get("durationMinutes") or 0),
        "reason": str(payload.get("reason") or "").strip(),
        "capabilities": sorted({str(v) for v in (payload.get("capabilities") or [])}),
    }
    replay = _same_or_conflict(
        _existing(_base.ELEVATION, 0, key), expected,
        fields=("requestId", "userId", "durationMinutes", "reason", "capabilities"),
    )
    return replay or _base.create_elevation(payload, actor=actor)


def create_support_session(payload: dict, *, actor: dict | None = None) -> dict:
    tenant_id = int(payload.get("tenantId") or 0)
    key = _base._idempotent_key("support", payload.get("requestId"))
    expected = {
        "requestId": payload.get("requestId"),
        "tenantId": tenant_id,
        "durationMinutes": int(payload.get("durationMinutes") or 0),
        "reason": str(payload.get("reason") or "").strip(),
        "incidentId": str(payload.get("incidentId") or ""),
        "scopes": sorted({str(v).strip() for v in (payload.get("scopes") or []) if str(v).strip()}),
    }
    replay = _same_or_conflict(
        _existing(_base.SUPPORT, tenant_id, key), expected,
        fields=("requestId", "tenantId", "durationMinutes", "reason", "incidentId", "scopes"),
    )
    return replay or _base.create_support_session(payload, actor=actor)


def create_access_review(payload: dict, *, actor: dict) -> dict:
    key = _base._idempotent_key("review", payload.get("requestId"))
    expected = {
        "requestId": payload.get("requestId"),
        "name": str(payload.get("name") or "Platform Access Review").strip(),
        "dueAt": payload.get("dueAt"),
    }
    replay = _same_or_conflict(
        _existing(_base.REVIEW, 0, key), expected,
        fields=("requestId", "name", "dueAt"),
    )
    return replay or _base.create_access_review(payload, actor=actor)


# All other canonical service functions/constants pass through unchanged.
for _name in dir(_base):
    if _name.startswith("_") or _name in globals():
        continue
    globals()[_name] = getattr(_base, _name)


def __getattr__(name: str):
    return getattr(_base, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_base)))
