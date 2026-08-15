"""B2 production runtime for Platform Workforce / PAM.

The base canonical service owns storage, validation and atomic writes.  This
runtime layer adds replay-safe creation plus the production-only controls that
must be checked against live authority data on every use:

- elevation requires recent MFA assurance;
- support sessions bind a real ``SupportTicket`` from the target tenant;
- ticket status/tenant/assignee are revalidated at runtime, so closing or
  reassigning a ticket immediately kills access without waiting for session TTL;
- optional Incident binding remains an additional constraint, never a substitute
  for the support-ticket authority;
- requestId replay never creates a second grant.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission
from app.core.platform_assurance import assert_recent_platform_auth
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


def _operator_int(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "").strip()
    if raw.startswith("db-"):
        raw = raw[3:]
    return int(raw) if raw.isdigit() else None


def _validate_support_ticket(tenant_id: int, ticket_id: object, *, user: dict | None) -> dict:
    """Validate the live customer-success ticket authority for support access."""
    try:
        tid = int(tenant_id)
        ticket_pk = int(str(ticket_id or ""))
    except (TypeError, ValueError):
        raise AppException(
            "SUPPORT_TICKET_REQUIRED",
            "受控协助必须绑定真实 SupportTicket 数字 ID",
            http_status=422,
        ) from None
    if tid <= 0 or ticket_pk <= 0:
        raise AppException("SUPPORT_TICKET_REQUIRED", "受控协助必须绑定真实 SupportTicket", http_status=422)

    from app.models.customer_success import SupportTicket

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(SupportTicket).where(
            SupportTicket.id == ticket_pk,
            SupportTicket.tenant_id == tid,
            SupportTicket.is_deleted.is_(False),
        ).limit(1)).first()
        if row is None:
            # Same response for nonexistent and cross-tenant tickets: do not expose
            # whether another school's ticket exists.
            raise AppException("SUPPORT_TICKET_NOT_AVAILABLE", "目标学校没有可用的受控协助工单", http_status=404)
        status = str(row.status or "").upper()
        if status not in {"OPEN", "IN_PROGRESS"}:
            raise AppException("SUPPORT_TICKET_CLOSED", "已解决或关闭的工单不能授权受控协助", http_status=409)
        operator_id = _operator_int(user)
        if row.assignee_user_id is not None and operator_id != int(row.assignee_user_id):
            raise AppException("SUPPORT_TICKET_ASSIGNEE_MISMATCH", "当前平台主管不是该工单负责人", http_status=403)
        return {
            "ticketId": str(row.id),
            "tenantId": str(row.tenant_id),
            "status": status,
            "severity": row.severity,
            "assigneeUserId": str(row.assignee_user_id) if row.assignee_user_id is not None else None,
            "version": int(row.version or 0),
        }
    finally:
        db.close()


def create_elevation(payload: dict, *, actor: dict | None = None) -> dict:
    # Privilege elevation is itself a step-up action.  Recent password/SSO auth
    # without a signed MFA ACR/AMR claim is insufficient.
    assert_recent_platform_auth(actor or {}, require_mfa=True)
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
    operator = str((actor or {}).get("userId") or "").strip()
    if tenant_id <= 0 or not operator:
        raise AppException("VALIDATION_ERROR", "受控协助必须绑定学校和已认证平台主管操作人")
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "受控协助必须填写至少5个字符的原因")
    scopes = sorted({str(value).strip() for value in (payload.get("scopes") or []) if str(value).strip()})
    unknown = sorted(set(scopes) - set(_base.SUPPORT_SCOPE_CATALOG))
    if not scopes or unknown:
        raise AppException(
            "SUPPORT_SCOPE_INVALID",
            "受控协助只能使用权威 Support Scope Catalog 的具体范围",
            http_status=422,
            details={"unknownScopes": unknown},
        )
    require_mfa = any(bool(_base.SUPPORT_SCOPE_CATALOG[scope]["requiresMfa"]) for scope in scopes)
    assurance = assert_recent_platform_auth(actor or {}, require_mfa=require_mfa)
    ticket = _validate_support_ticket(tenant_id, payload.get("ticketId"), user=actor)
    incident = None
    if payload.get("incidentId") not in (None, ""):
        incident = _base._validate_incident_binding(tenant_id, payload.get("incidentId"))

    duration = int(payload.get("durationMinutes") or 0)
    if duration <= 0 or duration > 120:
        raise AppException("VALIDATION_ERROR", "受控协助必须在1-120分钟内")
    key = _base._idempotent_key("support", payload.get("requestId"))
    incident_id = str(incident.get("incidentId")) if incident is not None else None
    expected = {
        "requestId": payload.get("requestId"),
        "tenantId": tenant_id,
        "durationMinutes": duration,
        "reason": reason,
        "ticketId": ticket["ticketId"],
        "incidentId": incident_id,
        "scopes": scopes,
    }
    replay = _same_or_conflict(
        _existing(_base.SUPPORT, tenant_id, key), expected,
        fields=("requestId", "tenantId", "durationMinutes", "reason", "ticketId", "incidentId", "scopes"),
    )
    if replay:
        return replay

    now = _base._legacy._now()
    data = {
        **{k: v for k, v in payload.items() if k not in {"operatorUserId", "id"}},
        "tenantId": tenant_id,
        "operatorUserId": operator,
        "ticketId": ticket["ticketId"],
        "ticketVersionAtGrant": ticket["version"],
        "ticketSeverity": ticket["severity"],
        "ticketAssigneeUserId": ticket["assigneeUserId"],
        "incidentId": incident_id,
        "scopes": scopes,
        "assurance": assurance,
        "startedAt": now.isoformat(timespec="seconds"),
        "expiresAt": (now + timedelta(minutes=duration)).isoformat(timespec="seconds"),
        "status": "ACTIVE",
        "bannerRequired": True,
    }
    return _base._save_atomic(
        _base.SUPPORT,
        data,
        tenant_id=tenant_id,
        audit_action="PLATFORM_SUPPORT_SESSION_CHANGE",
        audit_detail={
            "operatorUserId": operator,
            "ticketId": ticket["ticketId"],
            "incidentId": incident_id,
            "scopes": scopes,
            "reason": reason,
        },
        key=key,
        create_idempotent=True,
    )


def support_session_allows(session: dict, *, user: dict, tenant_id: int, scope: str, now=None) -> bool:
    if scope not in _base.SUPPORT_SCOPE_CATALOG:
        return False
    if not _base._legacy.support_session_allows(session, user=user, tenant_id=tenant_id, scope=scope, now=now):
        return False
    try:
        _validate_support_ticket(int(tenant_id), session.get("ticketId"), user=user)
        if session.get("incidentId") not in (None, ""):
            _base._validate_incident_binding(int(tenant_id), session.get("incidentId"))
    except Exception:
        return False
    return True


def assert_support_session(user: dict, *, tenant_id: int, scope: str, sessions: list[dict] | None = None) -> dict:
    if scope not in _base.SUPPORT_SCOPE_CATALOG:
        raise no_permission("未知受控协助范围；禁止浏览器自定义 scope")
    active = sessions if sessions is not None else _base.list_records(_base.SUPPORT, tenant_id=tenant_id)
    if not any(support_session_allows(item, user=user, tenant_id=tenant_id, scope=scope) for item in active):
        raise no_permission("缺少 ACTIVE、未到期、同租户、同操作人、同工单负责人且 scope 精确匹配的受控协助会话")
    return user


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
