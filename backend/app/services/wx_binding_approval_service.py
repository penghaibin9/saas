"""Independent, one-use school approval for password-channel WeChat enrollment.

The operator CLI is the only issuer. A namespaced AuthChallengeState row stores
only digests and subject/version bindings, never the bearer code or raw openid.
Consumption joins the binding writer's MySQL transaction, so audit failure rolls
back both enrollment and consumption. Redis is not an authorization authority.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth_hardening_policy import strict_security_environment
from app.core.config import settings
from app.core.exceptions import AppException

APPROVAL_TTL_SECONDS = 300
_PURPOSE = "WX_PASSWORD_BIND_APPROVAL"
_SCHOOL_TYPES = frozenset({"STUDENT", "TEACHER", "ADMIN", "STAFF", "SCHOOL_ADMIN"})
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{40,128}\Z")


def assert_school_wx_subject(user) -> None:
    kind = str(getattr(user, "user_type", "") or "").strip().upper()
    if kind not in _SCHOOL_TYPES:
        raise AppException("NO_PERMISSION", "该账号不允许使用学校微信登录通道", http_status=403)
    if str(user.status or "").upper() != "ACTIVE" or user.is_deleted:
        raise AppException("UNAUTHORIZED", "账号已停用或已失效", http_status=401)


def _binding(user, openid: str) -> dict:
    assert_school_wx_subject(user)
    if not isinstance(openid, str) or not openid or len(openid) > 64 or openid != openid.strip():
        raise AppException("UNAUTHORIZED", "微信绑定凭证无效", http_status=401)
    return {
        "purpose": _PURPOSE,
        "tenantId": str(user.tenant_id),
        "userId": str(user.id),
        "version": int(user.version or 0),
        "openidHash": hashlib.sha256(openid.encode("utf-8")).hexdigest(),
    }


def _token_hash(token: str) -> str:
    # Separate from CAPTCHA IDs even when the caller submits the same string.
    return hashlib.sha256((_PURPOSE + ":" + token).encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.utcnow()


def _invalid() -> AppException:
    return AppException("WX_BIND_APPROVAL_INVALID", "批准码无效、已过期或与当前账号/微信不匹配",
                        http_status=403)


def issue_in_session(db, *, tenant_id: int, user_id: int, expected_version: int,
                     openid: str, incident_ref: str, operator: str,
                     identity_verified: bool) -> dict:
    """Add approval + critical audit to caller's transaction; never commit here.

    The returned code MUST NOT be delivered until commit succeeds. A school
    password, active session or copied wxToken is not independent identity proof.
    This function is deliberately not mounted on any HTTP route.
    """
    incident = str(incident_ref or "").strip()
    actor = str(operator or "").strip()
    if (identity_verified is not True or tenant_id <= 0 or user_id <= 0
            or expected_version < 0 or not 3 <= len(incident) <= 120
            or not 1 <= len(actor) <= 100):
        raise AppException("VALIDATION_ERROR", "必须完成独立身份核验并提供明确的账号、版本及核验记录")
    from app.models import User
    from app.models.auth_risk import AuthChallengeState
    from app.services import audit_log, auth_service_db

    try:
        user = db.scalars(select(User).where(
            User.id == user_id, User.tenant_id == tenant_id, User.is_deleted.is_(False),
        ).with_for_update().execution_options(populate_existing=True)).one_or_none()
        if user is None:
            raise AppException("DATA_NOT_FOUND", "所选学校不存在该账号", http_status=404)
        binding = _binding(user, openid)
        if binding["version"] != expected_version:
            raise AppException("DATA_CONFLICT", "账号版本已变化，请重新检查并核验", http_status=409)
        auth_service_db._ensure_tenant_login_allowed(db, user)
        if not auth_service_db._role_contexts(db, user):
            raise AppException("NO_PERMISSION", "账号尚未分配有效岗位", http_status=403)
        token = secrets.token_urlsafe(32)
        approval_ref = "wxap-" + uuid.uuid4().hex
        db.add(AuthChallengeState(
            challenge_id_hash=_token_hash(token),
            payload_json={"binding": binding, "approvalRef": approval_ref},
            expires_at=_now() + timedelta(seconds=APPROVAL_TTL_SECONDS),
        ))
        audit_log.record_critical_in_session(
            db, "WX_BIND_APPROVAL_AUTHORIZED", f"user:{user.id}", tenant_id=tenant_id,
            detail={"approvalRef": approval_ref, "incidentRef": incident,
                    "accountVersion": binding["version"], "openidHash": binding["openidHash"],
                    "independentlyVerified": True},
            operator_name_override=actor,
        )
        db.flush()
        return {"bindingApprovalToken": token, "approvalRef": approval_ref,
                "expiresIn": APPROVAL_TTL_SECONDS}
    except SQLAlchemyError as exc:
        raise AppException("AUTH_STORE_UNAVAILABLE", "绑定批准存储不可用，未放行绑定", http_status=503) from exc


def consume_in_session(db, user, openid: str, token: str | None) -> str | None:
    """Lock and consume a matching approval, leaving commit/rollback to the caller.

    No memory or Redis allow-cache. A mismatched grant is not consumed. Only
    explicitly enabled non-production fixtures may enroll without an approval.
    Supplied codes are always checked, including in development.
    """
    expected = _binding(user, openid)
    if not token:
        if not strict_security_environment(settings) and settings.mock_login_enabled is True:
            return None
        raise AppException(
            "WX_BIND_APPROVAL_REQUIRED", "新增微信绑定需学校独立核验身份并提供一次性批准码",
            details={"action": "CONTACT_SCHOOL_ADMIN", "expiresIn": APPROVAL_TTL_SECONDS},
            http_status=403,
        )
    if not isinstance(token, str) or not _TOKEN_RE.fullmatch(token):
        raise _invalid()
    from app.models.auth_risk import AuthChallengeState

    try:
        row = db.scalars(select(AuthChallengeState).where(
            AuthChallengeState.challenge_id_hash == _token_hash(token),
        ).with_for_update().execution_options(populate_existing=True)).one_or_none()
        now = _now()
        payload = row.payload_json if row is not None else None
        if (row is None or row.consumed_at is not None or row.expires_at <= now
                or not isinstance(payload, dict) or payload.get("binding") != expected
                or not isinstance(payload.get("approvalRef"), str)
                or not 1 <= len(payload["approvalRef"]) <= 120):
            raise _invalid()
        row.consumed_at = now
        db.flush()
        return payload["approvalRef"]
    except SQLAlchemyError as exc:
        raise AppException("AUTH_STORE_UNAVAILABLE", "绑定批准存储不可用，未放行绑定", http_status=503) from exc
