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

SUPPORT_SCOPE_CATALOG = {
    "tenant.context.read": {"riskLevel": "MEDIUM", "requiresMfa": False},
    "tenant.audit.read": {"riskLevel": "HIGH", "requiresMfa": True},
    "identity.metadata.read": {"riskLevel": "HIGH", "requiresMfa": True},
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


def _save_atomic(
    config_type: str,
    payload: dict,
    *,
    tenant_id: int,
    audit_action: str,
    audit_detail: dict,
    expected_version: int | None = None,
    key: str | None = None,
    create_idempotent: bool = False,
) -> dict:
    from app.models import PlatformConfig
    from app.services import audit_log

    record_key = str(key or payload.get("id") or uuid.uuid4().hex)
    digest = _digest(payload)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == int(tenant_id),
            PlatformConfig.config_type == config_type,
            PlatformConfig.config_key == record_key,
            PlatformConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        if row is not None and create_idempotent:
            current = dict(row.config_json or {})
            if current.get("requestDigest") == digest:
                return _row_to_dict(row)
            raise AppException("IDEMPOTENCY_CONFLICT", "相同 requestId 已用于不同请求内容", http_status=409)
        if row is not None:
            if expected_version is None or int(expected_version) != _version(row.version):
                raise AppException("DATA_CONFLICT", "平台访问记录已更新，请刷新后重试", http_status=409)
            row.version = _version(row.version) + 1
        else:
            row = PlatformConfig(
                tenant_id=int(tenant_id), config_type=config_type, config_key=record_key,
                config_json={}, enabled=True,
            )
            db.add(row)
            db.flush()
        data = {k: v for k, v in payload.items() if k not in {"id", "version", "expectedVersion"}}
        data["requestDigest"] = digest
        row.config_json = data
        row.enabled = str(data.get("status") or "ACTIVE").upper() == "ACTIVE"
        audit_log.record_critical_in_session(
            db,
            audit_action,
            f"{config_type}:{record_key}",
            detail={**audit_detail, "recordKey": record_key, "recordStatus": data.get("status")},
            tenant_id=int(tenant_id),
            resource_id=record_key,
        )
        db.commit()
        db.refresh(row)
        return _row_to_dict(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save_access_assignment(payload: dict, *, actor: dict | None = None) -> dict:
    assert_recent_platform_auth(actor or {}, require_mfa=False)
    user_id = str(payload.get("userId") or "").strip()
    duty_code = str(payload.get("dutyCode") or "").upper()
    reason = str(payload.get("reason") or "").strip()
    if not user_id:
        raise AppException("VALIDATION_ERROR", "职责分配必须指定平台用户")
    if duty_code not in ASSIGNABLE_DUTIES:
        raise AppException("VALIDATION_ERROR", "未知或不可长期分配的平台职责")
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "职责分配必须填写至少5个字符的原因")
    starts = _legacy._parse(payload.get("startsAt") or payload.get("effectiveAt"))
    expires = _legacy._parse(payload.get("expiresAt"))
    if starts and expires and expires <= starts:
        raise AppException("VALIDATION_ERROR", "职责到期时间必须晚于生效时间")
    key = str(payload.get("id") or "").strip()
    create = not key
    if create:
        key = _idempotent_key("duty", payload.get("requestId"))
    return _save_atomic(
        ASSIGNMENT,
        {**payload, "userId": user_id, "dutyCode": duty_code, "status": str(payload.get("status") or "ACTIVE").upper()},
        tenant_id=0,
        audit_action="PLATFORM_DUTY_CHANGE",
        audit_detail={"targetUserId": user_id, "dutyCode": duty_code, "reason": reason},
        expected_version=payload.get("expectedVersion"),
        key=key,
        create_idempotent=create,
    )


def create_elevation(payload: dict, *, actor: dict | None = None) -> dict:
    assurance = assert_recent_platform_auth(actor or {}, require_mfa=False)
    user_id = str(payload.get("userId") or "").strip()
    if not user_id:
        raise AppException("VALIDATION_ERROR", "临时提升必须指定平台用户")
    duration = int(payload.get("durationMinutes") or 0)
    if duration <= 0 or duration > 240:
        raise AppException("VALIDATION_ERROR", "临时提升必须在1-240分钟内")
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "临时提升必须记录至少5个字符的原因")
    capabilities = {str(value) for value in (payload.get("capabilities") or [])}
    if not capabilities or not capabilities.issubset(KNOWN_CAPABILITIES):
        raise AppException("VALIDATION_ERROR", "临时提升只能授予已登记的具体能力，禁止通配")
    now = _legacy._now()
    key = _idempotent_key("elev", payload.get("requestId"))
    trusted = {k: v for k, v in payload.items() if k not in {"approvedBy", "approvedByUserId", "id"}}
    data = {
        **trusted,
        "userId": user_id,
        "reason": reason,
        "capabilities": sorted(capabilities),
        "approvedBy": str((actor or {}).get("userId") or "AUTHENTICATED_ACCESS_MANAGER"),
        "approvalEvidence": assurance,
        "startsAt": now.isoformat(timespec="seconds"),
        "expiresAt": (now + timedelta(minutes=duration)).isoformat(timespec="seconds"),
        "status": "ACTIVE",
    }
    return _save_atomic(
        ELEVATION, data, tenant_id=0,
        audit_action="PLATFORM_ELEVATION_CHANGE",
        audit_detail={"targetUserId": user_id, "capabilities": sorted(capabilities), "reason": reason},
        key=key, create_idempotent=True,
    )


def _validate_incident_binding(tenant_id: int, incident_id: object) -> dict:
    try:
        iid = int(str(incident_id or ""))
    except (TypeError, ValueError):
        raise AppException("SUPPORT_INCIDENT_REQUIRED", "当前系统只有 Incident 具备可验证权威绑定；请提供有效 incidentId", http_status=422) from None
    from app.services import incident_service
    incident = incident_service.get_incident(iid, include_internal=False)
    if str(incident.get("status") or "").upper() == "RESOLVED":
        raise AppException("SUPPORT_INCIDENT_CLOSED", "已解决事件不能新建受控协助会话", http_status=409)
    affected = {int(item.get("tenantId")) for item in (incident.get("affectedTenants") or []) if str(item.get("tenantId") or "").isdigit()}
    if int(tenant_id) not in affected:
        raise AppException("SUPPORT_INCIDENT_TENANT_MISMATCH", "事件与目标学校不匹配", http_status=403)
    return incident


def create_support_session(payload: dict, *, actor: dict | None = None) -> dict:
    tenant_id = int(payload.get("tenantId") or 0)
    operator = str((actor or {}).get("userId") or "").strip()
    if tenant_id <= 0 or not operator:
        raise AppException("VALIDATION_ERROR", "受控协助必须绑定学校和已认证平台主管操作人")
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "受控协助必须填写至少5个字符的原因")
    scopes = sorted({str(value).strip() for value in (payload.get("scopes") or []) if str(value).strip()})
    unknown = sorted(set(scopes) - set(SUPPORT_SCOPE_CATALOG))
    if not scopes or unknown:
        raise AppException(
            "SUPPORT_SCOPE_INVALID", "受控协助只能使用权威 Support Scope Catalog 的具体范围",
            http_status=422, details={"unknownScopes": unknown},
        )
    require_mfa = any(bool(SUPPORT_SCOPE_CATALOG[scope]["requiresMfa"]) for scope in scopes)
    assurance = assert_recent_platform_auth(actor or {}, require_mfa=require_mfa)
    incident = _validate_incident_binding(tenant_id, payload.get("incidentId"))
    if payload.get("ticketId") and not payload.get("incidentId"):
        raise AppException("SUPPORT_TICKET_AUTHORITY_UNAVAILABLE", "当前仓库没有可验证的 Support Ticket Authority，禁止仅凭浏览器 ticketId 授权", http_status=409)
    duration = int(payload.get("durationMinutes") or 0)
    if duration <= 0 or duration > 120:
        raise AppException("VALIDATION_ERROR", "受控协助必须在1-120分钟内")
    now = _legacy._now()
    key = _idempotent_key("support", payload.get("requestId"))
    data = {
        **{k: v for k, v in payload.items() if k not in {"operatorUserId", "id"}},
        "operatorUserId": operator,
        "incidentId": str(incident.get("incidentId")),
        "scopes": scopes,
        "assurance": assurance,
        "startedAt": now.isoformat(timespec="seconds"),
        "expiresAt": (now + timedelta(minutes=duration)).isoformat(timespec="seconds"),
        "status": "ACTIVE",
        "bannerRequired": True,
    }
    return _save_atomic(
        SUPPORT, data, tenant_id=tenant_id,
        audit_action="PLATFORM_SUPPORT_SESSION_CHANGE",
        audit_detail={"operatorUserId": operator, "incidentId": data["incidentId"], "scopes": scopes, "reason": reason},
        key=key, create_idempotent=True,
    )


def terminate_record(config_type: str, record_id: str, *, tenant_id: int, expected_version: int, reason: str, actor: dict) -> dict:
    assert_recent_platform_auth(actor, require_mfa=config_type == SUPPORT)
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "终止/撤销必须填写至少5个字符的原因")
    rows = [item for item in list_records(config_type, tenant_id=tenant_id if config_type == SUPPORT else None) if str(item.get("id")) == str(record_id)]
    if not rows:
        raise AppException("DATA_NOT_FOUND", "平台主管访问记录不存在", http_status=404)
    current = rows[0]
    action = {
        ASSIGNMENT: "PLATFORM_DUTY_CHANGE",
        ELEVATION: "PLATFORM_ELEVATION_CHANGE",
        SUPPORT: "PLATFORM_SUPPORT_SESSION_CHANGE",
    }.get(config_type)
    if not action:
        raise AppException("VALIDATION_ERROR", "不支持撤销该记录类型")
    data = {k: v for k, v in current.items() if k not in {"version", "enabled"}}
    data.update({"status": "TERMINATED" if config_type == SUPPORT else "REVOKED", "terminatedReason": reason, "terminatedBy": actor.get("userId")})
    return _save_atomic(
        config_type, data, tenant_id=int(tenant_id if config_type == SUPPORT else 0),
        audit_action=action, audit_detail={"reason": reason, "actorUserId": actor.get("userId")},
        expected_version=int(expected_version), key=str(record_id),
    )


def create_access_review(payload: dict, *, actor: dict) -> dict:
    assert_recent_platform_auth(actor, require_mfa=False)
    key = _idempotent_key("review", payload.get("requestId"))
    snapshots = []
    for config_type in (ASSIGNMENT, ELEVATION, SUPPORT):
        for item in list_records(config_type):
            if str(item.get("status") or "ACTIVE").upper() != "ACTIVE":
                continue
            snapshots.append({
                "itemKey": f"{config_type}:{item.get('tenantId')}:{item.get('id')}",
                "configType": config_type,
                "tenantId": int(item.get("tenantId") or 0),
                "recordId": str(item.get("id")),
                "version": _version(item.get("version")),
                "snapshot": {k: v for k, v in item.items() if k not in {"requestDigest"}},
                "decision": "PENDING",
            })
    data = {
        "requestId": payload.get("requestId"),
        "name": str(payload.get("name") or "Platform Access Review").strip(),
        "dueAt": payload.get("dueAt"),
        "status": "OPEN",
        "createdBy": actor.get("userId"),
        "items": snapshots,
    }
    return _save_atomic(
        REVIEW, data, tenant_id=0,
        audit_action="PLATFORM_ACCESS_REVIEW_CHANGE",
        audit_detail={"action": "CREATE", "itemCount": len(snapshots)},
        key=key, create_idempotent=True,
    )


def close_access_review(review_id: str, payload: dict, *, actor: dict) -> dict:
    assert_recent_platform_auth(actor, require_mfa=True)
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "关闭访问复核必须填写至少5个字符的原因")
    decisions = {str(item.get("itemKey")): str(item.get("decision") or "").upper() for item in (payload.get("decisions") or [])}
    invalid = {key: value for key, value in decisions.items() if value not in {"KEEP", "REVOKE"}}
    if invalid:
        raise AppException("VALIDATION_ERROR", "复核决定只能是 KEEP / REVOKE")
    from app.models import PlatformConfig
    from app.services import audit_log
    db = get_sessionmaker()()
    try:
        campaign = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0, PlatformConfig.config_type == REVIEW,
            PlatformConfig.config_key == str(review_id), PlatformConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        if campaign is None:
            raise AppException("DATA_NOT_FOUND", "访问复核不存在", http_status=404)
        expected_version = payload.get("expectedVersion")
        if expected_version is None or int(expected_version) != _version(campaign.version):
            raise AppException("DATA_CONFLICT", "访问复核已变化，请刷新后重试", http_status=409)
        data = dict(campaign.config_json or {})
        if str(data.get("status") or "").upper() != "OPEN":
            raise AppException("DATA_CONFLICT", "访问复核已关闭", http_status=409)
        resolved = []
        for item in data.get("items") or []:
            key = str(item.get("itemKey"))
            decision = decisions.get(key, "KEEP")
            item["decision"] = decision
            if decision == "REVOKE":
                target = db.scalars(select(PlatformConfig).where(
                    PlatformConfig.tenant_id == int(item.get("tenantId") or 0),
                    PlatformConfig.config_type == item.get("configType"),
                    PlatformConfig.config_key == item.get("recordId"),
                    PlatformConfig.is_deleted.is_(False),
                ).with_for_update()).first()
                if target is not None and _version(target.version) == _version(item.get("version")):
                    target_data = dict(target.config_json or {})
                    target_data["status"] = "REVOKED"
                    target_data["reviewRevokedBy"] = actor.get("userId")
                    target.config_json = target_data
                    target.enabled = False
                    target.version = _version(target.version) + 1
                    resolved.append(key)
                elif target is not None:
                    raise AppException("DATA_CONFLICT", f"复核项 {key} 在复核期间已变化", http_status=409)
        data["status"] = "CLOSED"
        data["closedBy"] = actor.get("userId")
        data["closeReason"] = reason
        campaign.config_json = data
        campaign.enabled = False
        campaign.version = _version(campaign.version) + 1
        audit_log.record_critical_in_session(
            db, "PLATFORM_ACCESS_REVIEW_CHANGE", f"review:{review_id}",
            detail={"action": "CLOSE", "revokedItems": resolved, "reason": reason},
            tenant_id=0, resource_id=str(review_id),
        )
        db.commit()
        db.refresh(campaign)
        return _row_to_dict(campaign)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


for _name in dir(_legacy):
    if _name.startswith("_") or _name in globals():
        continue
    globals()[_name] = getattr(_legacy, _name)
