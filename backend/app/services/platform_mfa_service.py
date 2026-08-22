"""Native platform TOTP enrollment and short-lived MFA step-up tokens.

Irreversible control-plane actions already require signed MFA ACR/AMR claims.
This service makes that requirement reachable for native database-backed platform
operators without weakening it: enrollment requires a fresh primary session plus
password re-authentication (or an already-MFA upstream session), TOTP secrets are
encrypted at rest in the existing global PlatformConfig authority, verification
is replay-safe under a row lock, and step-up tokens are deliberately short-lived
and have no refresh token.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime
from urllib.parse import quote, urlencode

from sqlalchemy import select

from app.core.context import get_request_meta
from app.core.exceptions import AppException, unauthorized
from app.core.field_crypto import decrypt_sensitive, encrypt_sensitive
from app.core.platform_assurance import assurance_state, assert_recent_platform_auth
from app.core.security import create_access_token, verify_password
from app.db.session import get_sessionmaker
from app.services import auth_risk_service as risk

_CONFIG_TYPE = "PLATFORM_MFA_TOTP"
_RISK_TYPE = "PLATFORM_MFA"
_TOTP_PERIOD_SECONDS = 30
_TOTP_DIGITS = 6
_TOTP_WINDOW = 1
_STEP_UP_TTL_SECONDS = 600
_ISSUER = "Student Lifecycle SaaS"


def _utc_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _subject_pk(user: dict | None) -> int:
    user = user or {}
    raw = str(user.get("userId") or "").strip()
    role = str(user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    if not raw.startswith("db-") or not raw[3:].isdigit() or not role.startswith("PLATFORM_"):
        raise AppException("NO_PERMISSION", "仅真实平台主管账号可配置平台 MFA", http_status=403)
    return int(raw[3:])


def _config_key(user_pk: int) -> str:
    return f"user:{int(user_pk)}"


def _row(db, user_pk: int, *, lock: bool = False):
    from app.models import PlatformConfig

    query = select(PlatformConfig).where(
        PlatformConfig.tenant_id == 0,
        PlatformConfig.config_type == _CONFIG_TYPE,
        PlatformConfig.config_key == _config_key(user_pk),
    )
    if lock:
        query = query.with_for_update()
    return db.scalars(query).first()


def _new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _secret_bytes(secret: str) -> bytes:
    text = str(secret or "").strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(text) % 8) % 8)
    try:
        return base64.b32decode(text + padding, casefold=True)
    except Exception as exc:  # noqa: BLE001
        raise AppException("PLATFORM_MFA_SECRET_INVALID", "平台主管 MFA 密钥损坏，请联系管理员", http_status=500) from exc


def _totp_for_counter(secret: str, counter: int) -> str:
    digest = hmac.new(_secret_bytes(secret), struct.pack(">Q", int(counter)), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{binary % (10 ** _TOTP_DIGITS):0{_TOTP_DIGITS}d}"


def _match_counter(secret: str, code: str, *, now: float | None = None) -> int | None:
    value = str(code or "").strip()
    if len(value) != _TOTP_DIGITS or not value.isdigit():
        return None
    current = int((time.time() if now is None else float(now)) // _TOTP_PERIOD_SECONDS)
    for offset in range(-_TOTP_WINDOW, _TOTP_WINDOW + 1):
        counter = current + offset
        if counter >= 0 and secrets.compare_digest(_totp_for_counter(secret, counter), value):
            return counter
    return None


def _request_ip() -> str:
    return str((get_request_meta() or {}).get("ip") or "unknown")


def _risk_key(user_pk: int) -> str:
    return f"platform-mfa:{int(user_pk)}\n{_request_ip()}"


def _attempt_guard(user_pk: int) -> None:
    from app.core.token_store import rate_limit

    if not rate_limit(f"platform-mfa:{int(user_pk)}:{_request_ip()}", 10, 60):
        raise AppException("RATE_LIMITED", "MFA 验证过于频繁，请稍后重试", http_status=429)
    remain = risk.login_locked(_risk_key(user_pk), risk_type=_RISK_TYPE, tenant_id=None)
    if remain is None:
        raise AppException("AUTH_RISK_STORE_UNAVAILABLE", "MFA 风控存储暂时不可用", http_status=503)
    if int(remain) > 0:
        raise AppException("PLATFORM_MFA_LOCKED", f"MFA 失败次数过多，请 {int(remain) // 60 + 1} 分钟后重试", http_status=429)


def _bad_attempt(user_pk: int) -> None:
    result = risk.record_failure(
        _risk_key(user_pk), threshold=5, lock_seconds=5 * 60,
        risk_type=_RISK_TYPE, tenant_id=None,
    )
    if result is None:
        raise AppException("AUTH_RISK_STORE_UNAVAILABLE", "MFA 风控存储暂时不可用", http_status=503)
    _count, locked = result
    if int(locked or 0) > 0:
        raise AppException("PLATFORM_MFA_LOCKED", "MFA 失败次数过多，已锁定 5 分钟", http_status=429)
    raise unauthorized("MFA 验证码无效")


def _reset_attempts(user_pk: int) -> None:
    risk.reset_failure(_risk_key(user_pk), risk_type=_RISK_TYPE, tenant_id=None)


def _assert_enrollment_authority(user: dict, password: str | None) -> int:
    user_pk = _subject_pk(user)
    assert_recent_platform_auth(user, require_mfa=False)
    if assurance_state(user)["mfa"]:
        return user_pk
    if not str(password or ""):
        raise AppException(
            "PLATFORM_PRIMARY_REAUTH_REQUIRED",
            "首次绑定 MFA 必须重新输入当前平台主管密码",
            http_status=403,
        )
    _attempt_guard(user_pk)
    from app.models import User

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(User).where(
            User.id == user_pk,
            User.is_deleted.is_(False),
            User.status == "ACTIVE",
        )).first()
        if row is None or not verify_password(str(password), row.password_hash):
            _bad_attempt(user_pk)
    finally:
        db.close()
    _reset_attempts(user_pk)
    return user_pk


def _provisioning_uri(secret: str, user: dict) -> str:
    account = str(user.get("loginName") or user.get("userId") or "platform")
    label = quote(f"{_ISSUER}:{account}", safe="")
    query = urlencode({
        "secret": secret,
        "issuer": _ISSUER,
        "algorithm": "SHA1",
        "digits": str(_TOTP_DIGITS),
        "period": str(_TOTP_PERIOD_SECONDS),
    })
    return f"otpauth://totp/{label}?{query}"


def enrollment_status(user: dict) -> dict:
    user_pk = _subject_pk(user)
    db = get_sessionmaker()()
    try:
        row = _row(db, user_pk)
        state = str(getattr(row, "status", "") or "NONE").upper() if row and not row.is_deleted else "NONE"
        return {
            "enabled": bool(row and not row.is_deleted and row.enabled and state == "ACTIVE"),
            "status": state,
            "method": "TOTP",
        }
    finally:
        db.close()


def start_enrollment(user: dict, *, password: str | None) -> dict:
    user_pk = _assert_enrollment_authority(user, password)
    secret = _new_secret()
    encrypted = encrypt_sensitive(secret, "platform_totp")
    if not encrypted:
        raise AppException("PLATFORM_MFA_SECRET_INVALID", "无法生成平台主管 MFA 密钥", http_status=500)

    from app.models import PlatformConfig

    db = get_sessionmaker()()
    try:
        row = _row(db, user_pk, lock=True)
        if row is not None and not row.is_deleted and str(row.status or "").upper() == "ACTIVE":
            raise AppException(
                "PLATFORM_MFA_ALREADY_ENROLLED",
                "当前平台主管已启用 MFA；轮换或恢复需走受控运维流程",
                http_status=409,
            )
        payload = {
            "secretEncrypted": encrypted,
            "method": "TOTP",
            "createdAt": _utc_iso(),
            "confirmedAt": None,
            "lastCounter": None,
            "lastStepUpAt": None,
        }
        if row is None:
            row = PlatformConfig(
                tenant_id=0,
                config_type=_CONFIG_TYPE,
                config_key=_config_key(user_pk),
                config_json=payload,
                enabled=False,
                status="PENDING",
                remark="Native platform TOTP MFA authority",
            )
            db.add(row)
        else:
            row.is_deleted = False
            row.config_json = payload
            row.enabled = False
            row.status = "PENDING"
            row.version = int(row.version or 0) + 1
        db.commit()
    finally:
        db.close()

    return {
        "status": "PENDING",
        "method": "TOTP",
        "secret": secret,
        "provisioningUri": _provisioning_uri(secret, user),
        "digits": _TOTP_DIGITS,
        "periodSeconds": _TOTP_PERIOD_SECONDS,
        "algorithm": "SHA1",
    }


def _step_up_claims(user: dict) -> dict:
    claims = {
        "userId": user.get("userId"),
        "loginName": user.get("loginName"),
        "realName": user.get("realName"),
        "userType": user.get("userType"),
        "tid": user.get("tenantCode"),
        "tenantId": str(user.get("tenantId") or "0"),
        "activeContextId": user.get("activeContextId"),
        "currentRoleCode": user.get("currentRoleCode"),
        "permissionVersion": user.get("permissionVersion"),
        "clientType": "PLATFORM_PC",
        "amr": sorted({*{str(v).lower() for v in (user.get("amr") or []) if str(v)}, "totp"}),
        "acr": "urn:student-lifecycle:assurance:mfa",
        "auth_time": int(time.time()),
    }
    if user.get("authSessionId"):
        claims["authSessionId"] = user["authSessionId"]
    return claims


def _token_result(user: dict) -> dict:
    return {
        "accessToken": create_access_token(_step_up_claims(user), expires_in=_STEP_UP_TTL_SECONDS),
        "tokenType": "Bearer",
        "expiresIn": _STEP_UP_TTL_SECONDS,
        "assurance": "MFA",
        "amr": ["totp"],
    }


def confirm_enrollment(user: dict, *, code: str) -> dict:
    user_pk = _subject_pk(user)
    assert_recent_platform_auth(user, require_mfa=False)
    _attempt_guard(user_pk)
    db = get_sessionmaker()()
    try:
        row = _row(db, user_pk, lock=True)
        if row is None or row.is_deleted or str(row.status or "").upper() != "PENDING":
            raise AppException("PLATFORM_MFA_ENROLLMENT_NOT_PENDING", "没有待确认的 MFA 绑定", http_status=409)
        data = dict(row.config_json or {})
        secret = decrypt_sensitive(data.get("secretEncrypted"), "platform_totp", allow_legacy_plaintext=False)
        counter = _match_counter(str(secret or ""), code)
        if counter is None:
            db.rollback()
            _bad_attempt(user_pk)
        data.update({"confirmedAt": _utc_iso(), "lastCounter": int(counter), "lastStepUpAt": _utc_iso()})
        row.config_json = data
        row.enabled = True
        row.status = "ACTIVE"
        row.version = int(row.version or 0) + 1
        db.commit()
    finally:
        db.close()
    _reset_attempts(user_pk)
    return {"enabled": True, "status": "ACTIVE", "method": "TOTP", **_token_result(user)}


def step_up(user: dict, *, code: str) -> dict:
    user_pk = _subject_pk(user)
    assert_recent_platform_auth(user, require_mfa=False)
    _attempt_guard(user_pk)
    db = get_sessionmaker()()
    try:
        row = _row(db, user_pk, lock=True)
        if row is None or row.is_deleted or not row.enabled or str(row.status or "").upper() != "ACTIVE":
            raise AppException("PLATFORM_MFA_NOT_ENROLLED", "当前平台主管尚未启用 MFA", http_status=409)
        data = dict(row.config_json or {})
        secret = decrypt_sensitive(data.get("secretEncrypted"), "platform_totp", allow_legacy_plaintext=False)
        counter = _match_counter(str(secret or ""), code)
        last_counter = int(data.get("lastCounter")) if data.get("lastCounter") is not None else -1
        if counter is None or int(counter) <= last_counter:
            db.rollback()
            _bad_attempt(user_pk)
        data.update({"lastCounter": int(counter), "lastStepUpAt": _utc_iso()})
        row.config_json = data
        row.version = int(row.version or 0) + 1
        db.commit()
    finally:
        db.close()
    _reset_attempts(user_pk)
    return _token_result(user)
