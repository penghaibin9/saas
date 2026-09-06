"""Canonical Platform Workforce / PAM service without new schema.

Until normalized PAM tables are migrated, PlatformConfig remains the storage
adapter. Runtime authorization, idempotency, state, critical audit and scope
catalog semantics are canonical here.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission
from app.core.platform_assurance import assert_recent_platform_auth
from app.db.session import get_sessionmaker
from app.modules.platform.services import platform_access_governance_legacy as _legacy

ASSIGNMENT = _legacy.ASSIGNMENT
ELEVATION = _legacy.ELEVATION
SUPPORT = _legacy.SUPPORT
REVIEW = _legacy.REVIEW
DUTY_CAPABILITIES = _legacy.DUTY_CAPABILITIES
ASSIGNABLE_DUTIES = _legacy.ASSIGNABLE_DUTIES
KNOWN_CAPABILITIES = _legacy.KNOWN_CAPABILITIES

# Exact support scopes are the server-side allow-list for temporary cross-tenant
# assistance. School-account mutations are intentionally limited to school-admin
# break-glass work; normal teacher/student account management belongs to the
# school's System Administration plane.
SUPPORT_SCOPE_CATALOG = {
    "tenant.context.read": {"riskLevel": "MEDIUM", "requiresMfa": False},
    "tenant.audit.read": {"riskLevel": "HIGH", "requiresMfa": True},
    "identity.metadata.read": {"riskLevel": "HIGH", "requiresMfa": True},
    "identity.admin.create": {"riskLevel": "CRITICAL", "requiresMfa": True},
    "identity.admin.status": {"riskLevel": "CRITICAL", "requiresMfa": True},
    "identity.admin.reset-password": {"riskLevel": "CRITICAL", "requiresMfa": True},
    "file.metadata.read": {"riskLevel": "HIGH", "requiresMfa": True},
    "sensitive.identity.read": {"riskLevel": "CRITICAL", "requiresMfa": True},
}


def _digest(payload: dict) -> str:
    body = {k: v for k, v in payload.items() if k not in {"expectedVersion"}}
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _idempotent_key(prefix: str, request_id: str) -> str:
    raw = str(request_id or "").strip()
    if len(raw) < 8:
        raise AppException("IDEMPOTENCY_KEY_REQUIRED", "高危平台主管创建操作必须提供至少8位 requestId", http_status=422)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:32]}"


def _row_to_dict(row) -> dict:
    return _legacy._row_to_dict(row)


def _version(value) -> int:
    """Preserve the valid initial optimistic-lock version 0; only NULL maps to 0."""
    return 0 if value is None else int(value)


def list_records(config_type: str, *, tenant_id: int | None = None) -> list[dict]:
    return _legacy.list_records(config_type, tenant_id=tenant_id)


def effective_platform_duties(user: dict, **kwargs):
    return _legacy.effective_platform_duties(user, **kwargs)


def assert_platform_capability(user: dict, capability: str, **kwargs):
    return _legacy.assert_platform_capability(user, capability, **kwargs)


def duty_matrix() -> list[dict]:
    """Explain fixed workforce duties without opening arbitrary duty creation."""
    import json
    from pathlib import Path
    from app.core.permission_catalog import load_permission_catalog

    root = Path(__file__).resolve().parents[5]
    surfaces = json.loads((root / "shared/contracts/navigation-surface-contract.json").read_text(encoding="utf-8")).get("surfaces") or []
    by_code = load_permission_catalog().get("_byCode") or {}
    result = []
    for duty in sorted(ASSIGNABLE_DUTIES):
        capabilities = sorted(DUTY_CAPABILITIES[duty])
        permissions = sorted(code for code in (f"platform.{capability}" for capability in capabilities) if code in by_code)
        permission_set = set(permissions)
        menus = [
            {field: item.get(field) for field in ("surfaceKey", "label", "path", "permissionKey")}
            for item in surfaces
            if item.get("platformOnly") and not item.get("hidden") and not item.get("disabled")
            and str(item.get("status") or "") in {"implemented", "partial"}
            and str(item.get("permissionKey") or "") in permission_set
        ]
        result.append({
            "dutyCode": duty,
            "capabilities": capabilities,
            "permissions": permissions,
            "menus": menus,
        })
    return result


# All remaining runtime behavior is provided by the established module body below.
# Keep this file content-compatible with the pre-existing implementation after the
# scope catalog/duty projection declarations above.


def _normalize_duties(raw) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        return set()
    return {str(value).strip() for value in values if str(value).strip() in ASSIGNABLE_DUTIES}


def _capabilities_for_duties(duties: set[str]) -> set[str]:
    result: set[str] = set()
    for duty in duties:
        result.update(DUTY_CAPABILITIES.get(duty, set()))
    return result


def _active_records(config_type: str, *, tenant_id: int | None = None) -> list[dict]:
    now = _legacy._now()
    rows = list_records(config_type, tenant_id=tenant_id)
    return [row for row in rows if _legacy._is_active_record(row, now=now)]


def create_access_assignment(payload: dict, *, actor: dict | None = None) -> dict:
    return _legacy.create_access_assignment(payload, actor=actor)


def create_elevation(payload: dict, *, actor: dict | None = None) -> dict:
    return _legacy.create_elevation(payload, actor=actor)


def _validate_incident_binding(tenant_id: int, incident_id: object) -> dict:
    return _legacy._validate_incident_binding(tenant_id, incident_id)


def create_support_session(payload: dict, *, actor: dict | None = None) -> dict:
    return _legacy.create_support_session(payload, actor=actor)


def create_access_review(payload: dict, *, actor: dict | None = None) -> dict:
    return _legacy.create_access_review(payload, actor=actor)


def close_access_review(review_id: str, payload: dict, *, actor: dict | None = None) -> dict:
    return _legacy.close_access_review(review_id, payload, actor=actor)


def terminate_record(config_type: str, record_id: str, *, tenant_id: int, expected_version: int, reason: str, actor: dict | None = None) -> dict:
    return _legacy.terminate_record(
        config_type, record_id, tenant_id=tenant_id,
        expected_version=expected_version, reason=reason, actor=actor,
    )


def support_session_allows(session: dict, *, user: dict, tenant_id: int, scope: str, now=None) -> bool:
    if scope not in SUPPORT_SCOPE_CATALOG:
        return False
    return _legacy.support_session_allows(session, user=user, tenant_id=tenant_id, scope=scope, now=now)


def assert_support_session(user: dict, *, tenant_id: int, scope: str, sessions: list[dict] | None = None) -> dict:
    if scope not in SUPPORT_SCOPE_CATALOG:
        raise no_permission("未知受控协助范围；禁止浏览器自定义 scope")
    active = sessions if sessions is not None else list_records(SUPPORT, tenant_id=tenant_id)
    if not any(support_session_allows(item, user=user, tenant_id=tenant_id, scope=scope) for item in active):
        raise no_permission("缺少 ACTIVE、未到期、同租户、同操作人且 scope 精确匹配的受控协助会话")
    return user


def __getattr__(name: str):
    return getattr(_legacy, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy)))
