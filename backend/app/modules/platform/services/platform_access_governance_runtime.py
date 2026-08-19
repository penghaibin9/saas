"""B2 production runtime for Platform Workforce / PAM.

The base canonical service owns storage, validation and atomic writes. This
runtime layer adds replay-safe creation plus the production-only controls that
must be checked against live authority data on every use:

- elevation requires recent MFA assurance;
- support sessions bind a real ``SupportTicket`` from the target tenant;
- ticket status/tenant/assignee are revalidated at runtime, so closing or
  reassigning a ticket immediately kills access without waiting for session TTL;
- optional Incident binding remains an additional constraint, never a substitute
  for the support-ticket authority;
- requestId replay never creates a second grant;
- access-review close requires one explicit decision for every frozen item;
- support-session self termination is distinct from cross-operator termination.
"""
from __future__ import annotations

import json
from collections import Counter
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
    # Privilege elevation is itself a step-up action. Recent password/SSO auth
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


def _review_decisions(payload: dict, expected_keys: set[str]) -> dict[str, str]:
    raw = payload.get("decisions")
    if not isinstance(raw, list):
        raise AppException(
            "ACCESS_REVIEW_DECISION_SET_INVALID",
            "访问复核关闭必须提交完整 decisions 列表",
            http_status=422,
            details={"missingItemKeys": sorted(expected_keys), "unknownItemKeys": [], "duplicateItemKeys": []},
        )
    submitted_keys = [str(item.get("itemKey") or "") if isinstance(item, dict) else "" for item in raw]
    counts = Counter(submitted_keys)
    duplicates = sorted(key for key, count in counts.items() if key and count > 1)
    submitted_set = {key for key in submitted_keys if key}
    missing = sorted(expected_keys - submitted_set)
    unknown = sorted(submitted_set - expected_keys)
    malformed = sum(1 for key in submitted_keys if not key)
    decisions = {
        str(item.get("itemKey")): str(item.get("decision") or "").upper()
        for item in raw if isinstance(item, dict) and str(item.get("itemKey") or "")
    }
    invalid = sorted(key for key, value in decisions.items() if value not in {"KEEP", "REVOKE"})
    if duplicates or missing or unknown or malformed or invalid or len(raw) != len(expected_keys):
        raise AppException(
            "ACCESS_REVIEW_DECISION_SET_INVALID",
            "访问复核必须对冻结快照中的每一项且仅一项提交 KEEP / REVOKE",
            http_status=422,
            details={
                "expectedCount": len(expected_keys),
                "submittedCount": len(raw),
                "missingItemKeys": missing[:100],
                "unknownItemKeys": unknown[:100],
                "duplicateItemKeys": duplicates[:100],
                "invalidDecisionItemKeys": invalid[:100],
                "malformedDecisionCount": malformed,
            },
        )
    return decisions


def close_access_review(review_id: str, payload: dict, *, actor: dict) -> dict:
    """Close one review atomically only with an exact decision set."""
    assert_recent_platform_auth(actor, require_mfa=True)
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "关闭访问复核必须填写至少5个字符的原因")

    from app.models import PlatformConfig
    from app.services import audit_log

    db = get_sessionmaker()()
    try:
        campaign = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == _base.REVIEW,
            PlatformConfig.config_key == str(review_id),
            PlatformConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        if campaign is None:
            raise AppException("DATA_NOT_FOUND", "访问复核不存在", http_status=404)
        expected_version = payload.get("expectedVersion")
        if expected_version is None or int(expected_version) != _base._version(campaign.version):
            raise AppException("DATA_CONFLICT", "访问复核已变化，请刷新后重试", http_status=409)
        data = dict(campaign.config_json or {})
        if str(data.get("status") or "").upper() != "OPEN":
            raise AppException("DATA_CONFLICT", "访问复核已关闭", http_status=409)

        items = list(data.get("items") or [])
        expected_keys = {str(item.get("itemKey")) for item in items if str(item.get("itemKey") or "")}
        if len(expected_keys) != len(items):
            raise AppException(
                "ACCESS_REVIEW_SNAPSHOT_INVALID",
                "访问复核冻结快照包含空或重复 itemKey，拒绝关闭",
                http_status=409,
            )
        decisions = _review_decisions(payload, expected_keys)

        resolved = []
        for item in items:
            key = str(item.get("itemKey"))
            decision = decisions[key]
            item["decision"] = decision
            if decision != "REVOKE":
                continue
            target = db.scalars(select(PlatformConfig).where(
                PlatformConfig.tenant_id == int(item.get("tenantId") or 0),
                PlatformConfig.config_type == item.get("configType"),
                PlatformConfig.config_key == item.get("recordId"),
                PlatformConfig.is_deleted.is_(False),
            ).with_for_update()).first()
            if target is None:
                raise AppException("DATA_CONFLICT", f"复核项 {key} 的目标记录已不存在", http_status=409)
            if _base._version(target.version) != _base._version(item.get("version")):
                raise AppException("DATA_CONFLICT", f"复核项 {key} 在复核期间已变化", http_status=409)
            target_data = dict(target.config_json or {})
            target_data["status"] = "REVOKED"
            target_data["reviewRevokedBy"] = actor.get("userId")
            target.config_json = target_data
            target.enabled = False
            target.version = _base._version(target.version) + 1
            resolved.append(key)

        data["items"] = items
        data["status"] = "CLOSED"
        data["closedBy"] = actor.get("userId")
        data["closeReason"] = reason
        campaign.config_json = data
        campaign.enabled = False
        campaign.version = _base._version(campaign.version) + 1
        audit_log.record_critical_in_session(
            db,
            "PLATFORM_ACCESS_REVIEW_CHANGE",
            f"review:{review_id}",
            detail={"action": "CLOSE", "revokedItems": resolved, "reason": reason},
            tenant_id=0,
            resource_id=str(review_id),
        )
        db.commit()
        db.refresh(campaign)
        return _base._row_to_dict(campaign)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def terminate_record(
    config_type: str,
    record_id: str,
    *,
    tenant_id: int,
    expected_version: int,
    reason: str,
    actor: dict,
) -> dict:
    """Separate support self-termination from cross-operator emergency termination."""
    if config_type == _base.SUPPORT:
        rows = [
            item for item in _base.list_records(_base.SUPPORT, tenant_id=int(tenant_id))
            if str(item.get("id")) == str(record_id)
        ]
        if not rows:
            raise AppException("DATA_NOT_FOUND", "受控协助会话不存在", http_status=404)
        owner_id = str(rows[0].get("operatorUserId") or "")
        actor_id = str((actor or {}).get("userId") or "")
        if owner_id != actor_id:
            _base.assert_platform_capability(actor, "access.manage")
    return _base.terminate_record(
        config_type,
        record_id,
        tenant_id=int(tenant_id),
        expected_version=int(expected_version),
        reason=reason,
        actor=actor,
    )


# All other canonical service functions/constants pass through unchanged.
for _name in dir(_base):
    if _name.startswith("_") or _name in globals():
        continue
    globals()[_name] = getattr(_base, _name)


def __getattr__(name: str):
    return getattr(_base, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_base)))