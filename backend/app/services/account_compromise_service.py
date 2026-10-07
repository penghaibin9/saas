"""Operator containment, not ordinary password change or account reactivation.

No commits here. Disable the subject, both WX sources and refresh credentials
in the SAME MySQL transaction, together with a mandatory audit record. A new
password / return to service requires the existing independent identity workflow.
"""
from __future__ import annotations

from sqlalchemy import delete, select, update
from app.core.exceptions import AppException


def contain_in_session(db, *, tenant_id: int, user_id: int, expected_version: int,
                       incident_ref: str, operator: str) -> dict:
    from app.models import AuthRefreshToken, User, WxAccountBinding
    from app.services import audit_log, auth_service_db
    if any(type(value) is not int for value in (tenant_id, user_id, expected_version)):
        raise ValueError("Tenant/user IDs and expected_version must be integers")
    incident_ref = str(incident_ref or "").strip()
    operator = str(operator or "").strip()
    if tenant_id <= 0 or user_id <= 0 or expected_version < 0:
        raise ValueError("Positive tenant/user IDs and expected_version are required")
    if not 3 <= len(incident_ref) <= 120 or not 1 <= len(operator) <= 100:
        raise ValueError("Bounded incident reference and operator are required")
    user = db.scalars(select(User).where(
        User.id == user_id, User.tenant_id == tenant_id, User.is_deleted.is_(False),
    ).with_for_update()).one_or_none()
    if user is None:
        raise AppException("DATA_NOT_FOUND", "目标账号不存在", http_status=404)
    if int(user.version or 0) != expected_version:
        raise AppException("DATA_CONFLICT", "账号版本已变化，请重新检查后执行", http_status=409)
    if str(user.user_type or "").strip().upper().startswith("PLATFORM"):
        raise AppException("NO_PERMISSION", "平台主管账号须使用独立应急流程", http_status=403)

    # Before the DB change: other workers must bypass stale subject snapshots.
    # Existing production implementation refuses the operation if Redis fails.
    auth_service_db.force_subject_revalidation(f"db-{user.id}", user.tenant_id)
    user.status = "DISABLED"
    user.must_change_password = True
    user.version = expected_version + 1
    user.credential_version = int(user.credential_version or 0) + 1
    user.wx_openid = None
    bindings = db.execute(update(WxAccountBinding).where(
        WxAccountBinding.tenant_id == tenant_id, WxAccountBinding.user_id == user_id,
        WxAccountBinding.is_deleted.is_(False),
    ).values(status="DISABLED"))
    refresh = db.execute(delete(AuthRefreshToken).where(AuthRefreshToken.user_id == f"db-{user_id}"))
    result = {"tenantId": str(tenant_id), "userId": str(user_id), "status": "DISABLED",
              "version": user.version, "wxBindingsDisabled": int(bindings.rowcount or 0),
              "refreshRevoked": int(refresh.rowcount or 0), "reactivated": False}
    audit_log.record_critical_in_session(
        db, "ACCOUNT_COMPROMISE_CONTAINED", f"user:{user_id}", tenant_id=tenant_id,
        detail={**result, "incidentRef": incident_ref}, operator_name_override=operator,
    )
    return result
