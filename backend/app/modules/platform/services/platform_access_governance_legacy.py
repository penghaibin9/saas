"""PLAT-15 platform duty, elevation and controlled school-support governance."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission
from app.core.permissions import has_permission
from app.db.session import get_sessionmaker

ASSIGNMENT = "PLATFORM_ACCESS_ASSIGNMENT"
ELEVATION = "PLATFORM_ELEVATION_SESSION"
SUPPORT = "PLATFORM_SUPPORT_SESSION"
REVIEW = "PLATFORM_ACCESS_REVIEW"

DUTY_CAPABILITIES = {
    "PLATFORM_OWNER": {"*"},
    "PLATFORM_COMMERCIAL": {"commercial.view", "commercial.manage", "tenant.view", "order.manage"},
    "PLATFORM_DELIVERY": {"tenant.view", "provisioning.manage", "support.request"},
    "PLATFORM_CUSTOMER_SUCCESS": {"tenant.view", "customerSuccess.manage", "support.request"},
    "PLATFORM_OPERATIONS": {"tenant.view", "operations.manage", "incident.manage", "support.request"},
    "PLATFORM_SECURITY_AUDITOR": {"audit.view", "access.review", "security.view"},
    "PLATFORM_SUPER_ADMIN": {"*"},
}

# Root control-plane identities are provisioned out-of-band and must never be
# created through the ordinary duty-assignment form.
ASSIGNABLE_DUTIES = {
    code for code in DUTY_CAPABILITIES
    if code not in {"PLATFORM_OWNER", "PLATFORM_SUPER_ADMIN"}
}
KNOWN_CAPABILITIES = {
    capability
    for capabilities in DUTY_CAPABILITIES.values()
    for capability in capabilities
    if capability != "*"
}


def _now() -> datetime:
    return datetime.utcnow()


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _role(user: dict) -> str:
    """Return only a platform-plane role; school roles never qualify."""
    for value in (user.get("currentRoleCode"), user.get("userType")):
        role = str(value or "").strip().upper()
        if role.startswith("PLATFORM_"):
            return role
    return ""


def _user_id(user: dict) -> str:
    return str(user.get("userId") or user.get("id") or "").strip()


def _is_active_record(item: dict, *, now: datetime) -> bool:
    if str(item.get("status") or "ACTIVE").upper() != "ACTIVE":
        return False
    starts, ends = _parse(item.get("startsAt") or item.get("effectiveAt")), _parse(item.get("expiresAt"))
    if starts and starts > now:
        return False
    if ends and ends <= now:
        return False
    return True


def _load_user_records(user: dict) -> tuple[list[dict], list[dict]]:
    user_id = _user_id(user)
    if not user_id or not _role(user):
        return [], []
    try:
        assignments = [item for item in list_records(ASSIGNMENT) if str(item.get("userId")) == user_id]
        elevations = [item for item in list_records(ELEVATION) if str(item.get("userId")) == user_id]
        return assignments, elevations
    except Exception:
        # Failure to read governance records never grants extra privilege.
        return [], []


def effective_platform_duties(
    user: dict,
    *,
    now: datetime | None = None,
    elevations: list[dict] | None = None,
    assignments: list[dict] | None = None,
) -> set[str]:
    now = now or _now()
    role = _role(user)
    if not role:
        # A school identity may hold school-side "*" but can never consume a
        # platform assignment/elevation record with a matching numeric user id.
        return set()
    user_id = _user_id(user)
    duties = set(DUTY_CAPABILITIES.get(role, set()))
    if assignments is None or elevations is None:
        stored_assignments, stored_elevations = _load_user_records(user)
        if assignments is None:
            assignments = stored_assignments
        if elevations is None:
            elevations = stored_elevations
    for item in assignments or []:
        if str(item.get("userId")) != user_id or not _is_active_record(item, now=now):
            continue
        duty_code = str(item.get("dutyCode") or "").upper()
        duties.update(DUTY_CAPABILITIES.get(duty_code, set()))
    for item in elevations or []:
        if str(item.get("userId")) != user_id or not _is_active_record(item, now=now):
            continue
        duties.update(str(value) for value in (item.get("capabilities") or []))
    return duties


def assert_platform_capability(user: dict, capability: str, *, elevations: list[dict] | None = None) -> dict:
    if not _role(user):
        raise no_permission("学校身份禁止访问平台控制面")
    duties = effective_platform_duties(user, elevations=elevations)
    if "*" not in duties and capability not in duties and not has_permission(user, f"platform.{capability}"):
        raise no_permission(f"平台职责不允许执行该操作（{capability}）")
    return user


def support_session_allows(
    session: dict,
    *,
    user: dict,
    tenant_id: int,
    scope: str,
    now: datetime | None = None,
) -> bool:
    now = now or _now()
    if not _role(user):
        return False
    if str(session.get("status") or "").upper() != "ACTIVE":
        return False
    if str(session.get("operatorUserId")) != _user_id(user):
        return False
    if int(session.get("tenantId") or 0) != int(tenant_id):
        return False
    if not session.get("ticketId") and not session.get("incidentId"):
        return False
    expires = _parse(session.get("expiresAt"))
    if not expires or expires <= now:
        return False
    scopes = {str(value) for value in (session.get("scopes") or [])}
    return scope in scopes


def assert_support_session(user: dict, *, tenant_id: int, scope: str, sessions: list[dict] | None = None) -> dict:
    active = sessions if sessions is not None else list_records(SUPPORT, tenant_id=tenant_id)
    if not any(support_session_allows(item, user=user, tenant_id=tenant_id, scope=scope) for item in active):
        raise no_permission("缺少绑定工单/事件、租户、范围和到期时间的受控协助会话")
    return user


def _row_to_dict(row) -> dict:
    payload = dict(row.config_json or {})
    return {
        "id": row.config_key,
        "tenantId": str(row.tenant_id),
        "enabled": bool(row.enabled),
        "version": int(row.version or 1),
        **payload,
    }


def list_records(config_type: str, *, tenant_id: int | None = None) -> list[dict]:
    from app.models import PlatformConfig

    db = get_sessionmaker()()
    try:
        query = select(PlatformConfig).where(
            PlatformConfig.config_type == config_type,
            PlatformConfig.is_deleted.is_(False),
        )
        if tenant_id is not None:
            query = query.where(PlatformConfig.tenant_id.in_((0, int(tenant_id))))
        rows = db.scalars(query.order_by(PlatformConfig.id.desc())).all()
        return [_row_to_dict(row) for row in rows]
    finally:
        db.close()


def save_record(
    config_type: str,
    payload: dict,
    *,
    tenant_id: int = 0,
    expected_version: int | None = None,
) -> dict:
    from app.models import PlatformConfig

    key = str(payload.get("id") or uuid.uuid4().hex)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == int(tenant_id),
            PlatformConfig.config_type == config_type,
            PlatformConfig.config_key == key,
            PlatformConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        if row:
            if expected_version is None or int(expected_version) != int(row.version or 1):
                raise AppException("DATA_CONFLICT", "平台访问记录已更新，请刷新后重试", http_status=409)
            row.version = int(row.version or 1) + 1
        else:
            row = PlatformConfig(
                tenant_id=int(tenant_id), config_type=config_type, config_key=key,
                config_json={}, enabled=True,
            )
            db.add(row)
        data = {k: v for k, v in payload.items() if k not in {"id", "version", "expectedVersion"}}
        row.config_json = data
        row.enabled = str(data.get("status") or "ACTIVE").upper() == "ACTIVE"
        db.commit()
        db.refresh(row)
        return _row_to_dict(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save_access_assignment(payload: dict) -> dict:
    user_id = str(payload.get("userId") or "").strip()
    duty_code = str(payload.get("dutyCode") or "").upper()
    if not user_id:
        raise AppException("VALIDATION_ERROR", "职责分配必须指定平台用户")
    if len(str(payload.get("reason") or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "职责分配必须填写至少5个字符的原因")
    if duty_code not in ASSIGNABLE_DUTIES:
        raise AppException("VALIDATION_ERROR", "未知或不可长期分配的平台职责")
    expires = _parse(payload.get("expiresAt"))
    starts = _parse(payload.get("startsAt") or payload.get("effectiveAt"))
    if expires and starts and expires <= starts:
        raise AppException("VALIDATION_ERROR", "职责到期时间必须晚于生效时间")
    return save_record(
        ASSIGNMENT,
        {**payload, "userId": user_id, "dutyCode": duty_code, "status": str(payload.get("status") or "ACTIVE").upper()},
        expected_version=payload.get("expectedVersion"),
    )


def create_elevation(payload: dict) -> dict:
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
    now = _now()
    trusted = {
        key: value for key, value in payload.items()
        if key not in {"approvedBy", "approvedByUserId"}
    }
    return save_record(ELEVATION, {
        **trusted,
        "userId": user_id,
        "reason": reason,
        "capabilities": sorted(capabilities),
        # The authenticated endpoint and security audit log are the approval
        # authority. A browser-supplied approver name is deliberately ignored.
        "approvedBy": "AUTHENTICATED_ACCESS_MANAGER",
        "approvalEvidence": "SECURITY_AUDIT_CONTEXT",
        "startsAt": now.isoformat(timespec="seconds"),
        "expiresAt": (now + timedelta(minutes=duration)).isoformat(timespec="seconds"),
        "status": "ACTIVE",
    })


def create_support_session(payload: dict) -> dict:
    tenant_id = int(payload.get("tenantId") or 0)
    operator_user_id = str(payload.get("operatorUserId") or "").strip()
    if tenant_id <= 0:
        raise AppException("VALIDATION_ERROR", "受控协助必须绑定学校")
    if not operator_user_id:
        raise AppException("VALIDATION_ERROR", "受控协助必须绑定平台操作人")
    if not payload.get("ticketId") and not payload.get("incidentId"):
        raise AppException("VALIDATION_ERROR", "受控协助必须绑定工单或事件")
    if len(str(payload.get("reason") or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "受控协助必须填写至少5个字符的原因")
    scopes = [str(value) for value in (payload.get("scopes") or []) if str(value)]
    if not scopes:
        raise AppException("VALIDATION_ERROR", "受控协助必须声明访问范围")
    if "*" in scopes:
        raise AppException("VALIDATION_ERROR", "受控协助禁止使用通配范围")
    duration = int(payload.get("durationMinutes") or 0)
    if duration <= 0 or duration > 120:
        raise AppException("VALIDATION_ERROR", "受控协助必须在1-120分钟内")
    now = _now()
    return save_record(SUPPORT, {
        **payload,
        "operatorUserId": operator_user_id,
        "scopes": scopes,
        "startedAt": now.isoformat(timespec="seconds"),
        "expiresAt": (now + timedelta(minutes=duration)).isoformat(timespec="seconds"),
        "status": "ACTIVE",
        "bannerRequired": True,
    }, tenant_id=tenant_id)
