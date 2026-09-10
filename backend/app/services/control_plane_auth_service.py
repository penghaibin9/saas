"""Production auth execution closure for control-plane P0 A/B.

This module is intentionally additive.  ``control_plane_p0_auth_guard.install``
rebinds the existing public service symbols and the router replaces only the
five password-bearing endpoints, preserving URLs and response contracts while
moving enforcement onto durable risk state + explicit effective policy.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.context import get_request_meta
from app.core.exceptions import AppException, unauthorized
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.db.session import db_enabled, get_sessionmaker
from app.services import auth_service_db
from app.services.auth_challenge_service import PLATFORM_LOGIN, WX_BIND, login_guard_key
from app.services import auth_risk_service as risk
from app.services.effective_security_policy_service import (
    PLATFORM,
    TENANT,
    resolve_for_claims,
    resolve_for_user,
    resolve_login_policy,
    resolve_tenant_id,
)

_DEV_BUCKETS: dict[str, deque] = defaultdict(deque)


def _tok_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _plane(client_type: str | None, user=None) -> str:
    if str(client_type or "").strip().upper() == "PLATFORM_PC":
        return PLATFORM
    if user is not None and str(getattr(user, "user_type", "") or "").upper() in {"PLATFORM_OP", "PLATFORM_SUPER_ADMIN"}:
        return PLATFORM
    return TENANT


def _ip() -> str:
    return str((get_request_meta() or {}).get("ip") or "unknown")


def rate_limit(bucket: str, limit: int, window: int = 60) -> bool:
    """Redis fast-path, MySQL fallback; process memory only outside strict env."""
    from app.core.redis_client import fixed_window_allow

    shared = fixed_window_allow(bucket, int(limit), int(window))
    if shared is not None:
        return bool(shared)
    fallback = risk.fixed_window_allow(bucket, int(limit), int(window))
    if fallback is not None:
        return bool(fallback)
    if risk.strict_env():
        raise AppException("AUTH_RISK_STORE_UNAVAILABLE", "认证限流存储暂时不可用", http_status=503)
    q = _DEV_BUCKETS[bucket]
    now = time.time()
    while q and q[0] <= now - int(window):
        q.popleft()
    if len(q) >= int(limit):
        return False
    q.append(now)
    return True


def login_rate_guard() -> None:
    if not rate_limit(f"login:{_ip()}", 10, 60):
        raise AppException("RATE_LIMITED", "登录过于频繁，请 1 分钟后再试", http_status=429)


def _risk_types(plane: str) -> tuple[str, str, str]:
    if plane == PLATFORM:
        return risk.PLATFORM_ACCOUNT, risk.PLATFORM_ACCOUNT_IP, risk.PLATFORM_IP
    return risk.LOGIN_ACCOUNT, risk.LOGIN_ACCOUNT_IP, risk.LOGIN_IP


def _risk_keys(lock_key: str) -> tuple[str, str, str]:
    ip = _ip()
    return lock_key, f"{lock_key}\n{ip}", ip


def _remaining_lock(lock_key: str, *, tenant_id: int | None, plane: str) -> int:
    types = _risk_types(plane)
    keys = _risk_keys(lock_key)
    remains = [
        int(risk.login_locked(key, risk_type=kind, tenant_id=tenant_id) or 0)
        for kind, key in zip(types, keys)
    ]
    return max(remains or [0])


def _record_bad_password(lock_key: str, *, tenant_id: int | None, plane: str, policy: dict) -> tuple[int, int]:
    types = _risk_types(plane)
    keys = _risk_keys(lock_key)
    threshold = int(policy["loginFailMaxTimes"])
    lock_seconds = int(policy["loginFailLockMinutes"]) * 60
    account = risk.record_failure(
        keys[0], threshold=threshold, lock_seconds=lock_seconds,
        risk_type=types[0], tenant_id=tenant_id,
    )
    risk.record_failure(
        keys[1], threshold=threshold, lock_seconds=lock_seconds,
        risk_type=types[1], tenant_id=tenant_id,
    )
    # IP-only bucket has a wider threshold to avoid one shared-campus NAT
    # account causing a lock while still bounding distributed password spray.
    risk.record_failure(
        keys[2], threshold=max(20, threshold * 4), lock_seconds=lock_seconds,
        risk_type=types[2], tenant_id=tenant_id,
    )
    if account is None:
        raise AppException("AUTH_RISK_STORE_UNAVAILABLE", "认证风控存储暂时不可用", http_status=503)
    return account


def _reset_account_risk(lock_key: str, *, tenant_id: int | None, plane: str) -> None:
    types = _risk_types(plane)
    keys = _risk_keys(lock_key)
    risk.reset_failure(keys[0], risk_type=types[0], tenant_id=tenant_id)
    risk.reset_failure(keys[1], risk_type=types[1], tenant_id=tenant_id)
    # Do not reset the IP-only spray bucket after one successful credential.


def login_locked_compat(key: str) -> int:
    return int(risk.login_locked(key, risk_type=risk.LOGIN_ACCOUNT) or 0)


def record_login_failure_compat(key: str, threshold: int | None = None,
                                lock_seconds: int | None = None) -> tuple[int, int]:
    result = risk.record_failure(
        key,
        threshold=int(threshold or 5),
        lock_seconds=int(lock_seconds or 15 * 60),
        risk_type=risk.LOGIN_ACCOUNT,
    )
    if result is None:
        raise AppException("AUTH_RISK_STORE_UNAVAILABLE", "认证风控存储暂时不可用", http_status=503)
    return result


def failure_count_compat(key: str) -> int:
    return int(risk.failure_count(key, risk_type=risk.LOGIN_ACCOUNT) or 0)


def reset_login_failures_compat(key: str) -> None:
    risk.reset_failure(key, risk_type=risk.LOGIN_ACCOUNT)


def _resolved_login_user(db, tenant_code, login_name, identifier_type):
    if identifier_type == "PHONE":
        from app.services.phone_login_service import require_phone_identifier, resolve_verified_phone_user
        phone = require_phone_identifier(tenant_code, login_name)
        tenant_id = resolve_tenant_id(tenant_code)
        return resolve_verified_phone_user(db, tenant_id=tenant_id, phone=phone) if tenant_id else None
    if identifier_type != "ACCOUNT":
        raise AppException("VALIDATION_ERROR", "不支持的登录方式", http_status=422)
    return auth_service_db._find_login_user(db, login_name, tenant_code)


def _subject_risk_key(tenant_code, login_name, user):
    # A verified alias and the original account share the same durable subject bucket.
    return login_guard_key(str(user.tenant_id), f"user:{user.id}") if user is not None else login_guard_key(tenant_code, login_name)


def captcha_required(scene: str, tenant_code: str | None, login_name: str | None, identifier_type: str = "ACCOUNT") -> bool:
    scene = str(scene or "").strip().upper()
    if scene == PLATFORM_LOGIN:
        return True
    plane = PLATFORM if scene == PLATFORM_LOGIN else TENANT
    tenant_id = None if plane == PLATFORM else resolve_tenant_id(tenant_code)
    with get_sessionmaker()() as db:
        user = _resolved_login_user(db, tenant_code, login_name, identifier_type)
        key = _subject_risk_key(tenant_code, login_name, user)
        if user is not None:
            tenant_id = int(user.tenant_id)
    policy = resolve_login_policy(tenant_id=tenant_id, principal_plane=plane)
    kind = risk.PLATFORM_ACCOUNT if plane == PLATFORM else risk.LOGIN_ACCOUNT
    count = risk.failure_count(key, risk_type=kind, tenant_id=tenant_id)
    if count is None:
        raise AppException("AUTH_RISK_STORE_UNAVAILABLE", "认证风控存储暂时不可用", http_status=503)
    return int(count) >= int(policy["captchaAfterFailures"])


def store_challenge(challenge_id: str, payload: dict, ttl: int) -> None:
    if risk.store_challenge(challenge_id, payload, ttl):
        return
    raise AppException("AUTH_RISK_STORE_UNAVAILABLE", "验证码存储暂时不可用", http_status=503)


def consume_challenge(challenge_id: str) -> dict | None:
    return risk.consume_challenge(challenge_id)


def issue_refresh(claims: dict, *, expires_in: int | None = None) -> str:
    """Backward-compatible refresh issuer with policy-controlled TTL."""
    from app.core import token_store

    ttl = max(60, int(expires_in or token_store.REFRESH_TTL))
    token = secrets.token_urlsafe(48)
    must_persist = risk.strict_env() or db_enabled()
    if db_enabled():
        db = get_sessionmaker()()
        try:
            from app.models import AuthRefreshToken

            db.add(AuthRefreshToken(
                token_hash=_tok_hash(token),
                user_id=str((claims or {}).get("userId") or ""),
                claims_json=dict(claims or {}),
                expires_at=datetime.utcnow() + timedelta(seconds=ttl),
            ))
            db.commit()
            return token
        except Exception as exc:  # noqa: BLE001
            try:
                db.rollback()
            except Exception:
                pass
            if must_persist:
                raise AppException("AUTH_STORE_UNAVAILABLE", "无法签发刷新令牌：认证存储写入失败", http_status=503) from exc
        finally:
            db.close()
    if must_persist:
        raise AppException("AUTH_STORE_UNAVAILABLE", "无法签发刷新令牌：认证存储不可用", http_status=503)
    token_store._refresh[token] = {"claims": dict(claims or {}), "exp": token_store._now() + ttl}
    return token


def _login_result(db, user, context: dict, contexts: list[dict], client_type: str) -> dict:
    policy = resolve_for_user(user, client_type)
    claims = auth_service_db._claims(db, user, context, contexts, client_type)
    claims["securityPolicyRevision"] = policy["policyRevision"]
    claims["securityPolicyDataQuality"] = policy["dataQuality"]
    access_seconds = int(policy["accessTokenExpireMinutes"]) * 60
    refresh_seconds = int(policy["refreshTokenExpireDays"]) * 24 * 3600
    access_token = create_access_token(dict(claims), expires_in=access_seconds)
    refresh_token = issue_refresh(dict(claims), expires_in=refresh_seconds)
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "tokenType": "Bearer",
        "expiresIn": access_seconds,
        "userId": f"db-{user.id}",
        "username": user.login_name,
        "displayName": user.real_name,
        "tenantId": str(user.tenant_id),
        "tenantName": claims["tenantName"],
        "activeContextId": context["contextId"],
        "currentRole": {
            "roleCode": context["roleCode"], "roleName": context["roleName"],
            "contextType": context["roleCode"], "contextName": context["roleName"],
            "dataScope": context["dataScope"], "scopeLabel": context["scopeLabel"],
        },
        "roles": [{"roleCode": c["roleCode"], "roleName": c["roleName"], "contextId": c["contextId"]} for c in contexts],
        "contexts": [{k: v for k, v in c.items() if k != "version"} for c in contexts],
        "dataScope": {"scope": context["dataScope"], "scopeLabel": context["scopeLabel"]},
        "permissionActions": {
            "viewList": True,
            "export": context["roleCode"] not in ("STUDENT", "PLATFORM_SUPER_ADMIN"),
            "viewSensitive": False,
        },
        "securityPolicy": {
            "revision": policy["policyRevision"],
            "source": policy["policySource"],
            "dataQuality": policy["dataQuality"],
        },
        "user": {
            "userId": f"db-{user.id}",
            "realName": user.real_name,
            "userType": user.user_type,
            "mustChangePassword": bool(user.must_change_password),
        },
    }


def build_login_result(db, user, client_type: str = "PC") -> dict:
    if str(client_type or "").upper() in {"MP", "STUDENT_MINI", "TEACHER_MINI"}:
        from app.services.wx_binding_approval_service import assert_school_wx_subject
        assert_school_wx_subject(user)
    auth_service_db._ensure_tenant_login_allowed(db, user)
    contexts = auth_service_db._role_contexts(db, user)
    if not contexts:
        raise AppException("NO_PERMISSION", "账号尚未分配有效岗位，请联系学校管理员")
    return _login_result(db, user, contexts[0], contexts, client_type)


def login_with_password(login_name: str, password: str, tenant_code: str | None = None,
                        client_type: str = "PC", *, identifier_type: str = "ACCOUNT") -> dict:
    if not db_enabled():
        raise AppException("UNAUTHORIZED", "账号密码登录需启用数据库（DB_ENABLED=true）")
    login_name = str(login_name or "").strip()
    audit_subject = "PHONE_LOGIN" if identifier_type == "PHONE" else login_name
    tenant_code = str(tenant_code or "").strip() or None
    plane = _plane(client_type)
    db = get_sessionmaker()()
    try:
        user = _resolved_login_user(db, tenant_code, login_name, identifier_type)
        if user is not None:
            # User first, binding second: serialize password verification/signing with security writers.
            db.refresh(user, with_for_update=True)
            if user.is_deleted or user.status != "ACTIVE":
                user = None
            elif identifier_type == "PHONE":
                from app.models import PhoneLoginBinding
                from app.services.phone_login_service import normalize_login_phone, phone_lookup
                binding = db.scalar(select(PhoneLoginBinding).where(
                    PhoneLoginBinding.tenant_id == user.tenant_id, PhoneLoginBinding.user_id == user.id,
                    PhoneLoginBinding.state == "VERIFIED", PhoneLoginBinding.is_deleted.is_(False),
                    PhoneLoginBinding.active_phone_lookup == phone_lookup(user.tenant_id, normalize_login_phone(login_name)),
                ).with_for_update().execution_options(populate_existing=True))
                if binding is None:
                    user = None
        # Resolved aliases share a lock. Unknown identifiers remain non-enumerating.
        lock_key = _subject_risk_key(tenant_code, login_name, user)
        tenant_id = None if plane == PLATFORM else (int(user.tenant_id) if user is not None else resolve_tenant_id(tenant_code))
        policy = resolve_login_policy(tenant_id=tenant_id, principal_plane=plane)
        remain = _remaining_lock(lock_key, tenant_id=tenant_id, plane=plane)
        if remain > 0:
            from app.services import audit_log
            audit_log.record(
                "LOGIN_LOCKED", audit_subject,
                detail={"remainSeconds": remain, "tenantCode": tenant_code, "policyRevision": policy["policyRevision"]},
                result="DENIED", tenant_id=tenant_id,
            )
            raise AppException("UNAUTHORIZED", f"失败次数过多，账号已锁定，请 {remain // 60 + 1} 分钟后再试")

        platform_account = bool(user and str(user.user_type or "").upper() in {"PLATFORM_OP", "PLATFORM_SUPER_ADMIN"})
        if user and platform_account != (plane == PLATFORM):
            user = None
        client = str(client_type or "").upper()
        if user and ((client == "STUDENT_MINI" and user.user_type != "STUDENT") or
                     (client == "TEACHER_MINI" and user.user_type not in {"TEACHER", "STAFF", "ADMIN", "SCHOOL_ADMIN"})):
            user = None
        if user is None or not verify_password(password or "", user.password_hash):
            from app.services import audit_log
            count, locked = _record_bad_password(lock_key, tenant_id=tenant_id, plane=plane, policy=policy)
            audit_log.record(
                "LOGIN_FAIL", audit_subject,
                detail={
                    "failCount": count, "locked": bool(locked), "tenantCode": tenant_code,
                    "policyRevision": policy["policyRevision"], "policyQuality": policy["dataQuality"],
                },
                result="FAIL", tenant_id=tenant_id,
            )
            if locked:
                raise AppException("UNAUTHORIZED", f"失败次数过多，账号已锁定 {policy['loginFailLockMinutes']} 分钟")
            if count >= int(policy["captchaAfterFailures"]):
                scene = PLATFORM_LOGIN if plane == PLATFORM else "PASSWORD_LOGIN"
                raise AppException(
                    "CAPTCHA_REQUIRED", "账号、学校编码或密码不正确，请输入验证码后继续",
                    details={"captchaRequired": True, "scene": scene}, http_status=401,
                )
            raise AppException("UNAUTHORIZED", "账号、学校编码或密码不正确")

        contexts = auth_service_db._role_contexts(db, user)
        if not contexts:
            from app.services import audit_log
            audit_log.record(
                "LOGIN_NO_ACTIVE_ROLE", audit_subject,
                detail={"tenantId": str(user.tenant_id)}, result="DENIED", tenant_id=int(user.tenant_id),
            )
            raise AppException("NO_PERMISSION", "账号尚未分配有效岗位，请联系学校管理员")
        auth_service_db._ensure_tenant_login_allowed(db, user)
        _reset_account_risk(lock_key, tenant_id=tenant_id, plane=plane)
        return _login_result(db, user, contexts[0], contexts, client_type)
    finally:
        db.close()


def refresh(refresh_token: str) -> dict:
    from app.core.token_store import consume_refresh

    claims = consume_refresh(refresh_token)
    if not claims:
        raise unauthorized("refreshToken 无效或已使用，请重新登录")
    auth_service_db.validate_token_subject(claims)
    policy = resolve_for_claims(claims)
    claims = dict(claims)
    claims["securityPolicyRevision"] = policy["policyRevision"]
    claims["securityPolicyDataQuality"] = policy["dataQuality"]
    access_seconds = int(policy["accessTokenExpireMinutes"]) * 60
    refresh_seconds = int(policy["refreshTokenExpireDays"]) * 24 * 3600
    return {
        "accessToken": create_access_token(claims, expires_in=access_seconds),
        "refreshToken": issue_refresh(claims, expires_in=refresh_seconds),
        "tokenType": "Bearer",
        "expiresIn": access_seconds,
        "securityPolicy": {
            "revision": policy["policyRevision"],
            "source": policy["policySource"],
            "dataQuality": policy["dataQuality"],
        },
    }


def change_own_password(user_ctx: dict, old_password: str, new_password: str) -> dict:
    if not db_enabled():
        raise AppException("UNAUTHORIZED", "需启用数据库")
    raw_id = str((user_ctx or {}).get("userId") or "")
    raw_tid = str((user_ctx or {}).get("tenantId") or "")
    if not raw_id.startswith("db-") or not raw_id[3:].isdigit() or not raw_tid.isdigit():
        raise AppException("VALIDATION_ERROR", "演示账号不支持修改密码，请使用正式账号登录后再试")
    tenant_id = int(raw_tid)
    policy = resolve_login_policy(tenant_id=tenant_id, principal_plane=TENANT)
    min_len = int(policy["passwordMinLength"])
    if len(new_password or "") < min_len:
        raise AppException("VALIDATION_ERROR", f"新密码长度至少 {min_len} 位")
    if old_password == new_password:
        raise AppException("VALIDATION_ERROR", "新密码不能与原密码相同")
    lock_key = f"pwchange:{tenant_id}:{raw_id[3:]}"
    remain = int(risk.login_locked(lock_key, risk_type="PASSWORD_CHANGE", tenant_id=tenant_id) or 0)
    if remain > 0:
        raise AppException("UNAUTHORIZED", f"失败次数过多，请 {remain // 60 + 1} 分钟后再试")
    db = get_sessionmaker()()
    try:
        user = auth_service_db._load_token_user(db, user_ctx)
        db.refresh(user, with_for_update=True)
        auth_service_db.validate_credential_epoch(user, user_ctx)
        if user.is_deleted or user.status != "ACTIVE":
            raise unauthorized("账号已停用，请重新登录")
        if not verify_password(old_password or "", user.password_hash):
            result = risk.record_failure(
                lock_key,
                threshold=int(policy["loginFailMaxTimes"]),
                lock_seconds=int(policy["loginFailLockMinutes"]) * 60,
                risk_type="PASSWORD_CHANGE", tenant_id=tenant_id,
            )
            if result is None:
                raise AppException("AUTH_RISK_STORE_UNAVAILABLE", "认证风控存储暂时不可用", http_status=503)
            _, locked = result
            if locked:
                raise AppException("UNAUTHORIZED", f"失败次数过多，账号已锁定 {policy['loginFailLockMinutes']} 分钟")
            raise AppException("UNAUTHORIZED", "原密码不正确")
        risk.reset_failure(lock_key, risk_type="PASSWORD_CHANGE", tenant_id=tenant_id)
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.version = int(user.version or 0) + 1
        user.credential_version = int(getattr(user, "credential_version", 0) or 0) + 1
        from app.services import audit_log
        audit_log.record_critical_in_session(db, "PASSWORD_CHANGE", f"user:{user.id}",
            detail={"credentialVersion": user.credential_version, "policyRevision": policy["policyRevision"]},
            tenant_id=user.tenant_id, resource_id=str(user.id))
        auth_service_db.force_subject_revalidation(f"db-{user.id}", user.tenant_id)
        db.commit()
        return auth_service_db.credential_change_receipt(user, user_ctx)
    finally:
        db.close()


def wx_bind(wx_token: str, login_name: str, password: str, tenant_code: str | None = None,
            *, binding_approval_token: str | None = None) -> dict:
    if not db_enabled():
        raise AppException("UNAUTHORIZED", "微信登录需启用数据库（DB_ENABLED=true）")
    try:
        claims = decode_token(wx_token)
    except Exception:
        raise AppException("UNAUTHORIZED", "微信绑定令牌无效或已过期，请重新发起微信登录")
    if claims.get("purpose") != "wx_bind" or not claims.get("wxOpenid"):
        raise AppException("UNAUTHORIZED", "微信绑定令牌无效")
    openid = claims["wxOpenid"]
    login_name = str(login_name or "").strip()
    normalized_tenant = str(tenant_code or "").strip() or None
    if not login_name or not password:
        raise AppException("VALIDATION_ERROR", "请输入学号/工号与密码")
    lock_key = login_guard_key(normalized_tenant, login_name)
    db = get_sessionmaker()()
    try:
        user = auth_service_db._find_login_user(db, login_name, normalized_tenant)
        tenant_id = int(user.tenant_id) if user is not None else resolve_tenant_id(normalized_tenant)
        policy = resolve_login_policy(tenant_id=tenant_id, principal_plane=TENANT)
        remain = _remaining_lock(lock_key, tenant_id=tenant_id, plane=TENANT)
        if remain > 0:
            raise AppException("UNAUTHORIZED", f"失败次数过多，账号已锁定，请 {remain // 60 + 1} 分钟后再试")
        # Serialize with recovery/password writes. Recheck all state after locking.
        if user is not None:
            db.refresh(user, with_for_update=True)
            if (str(user.status or "").upper() != "ACTIVE" or user.is_deleted
                    or str(user.user_type or "").upper().startswith("PLATFORM")):
                user = None
        if user is None or not verify_password(password, user.password_hash):
            count, locked = _record_bad_password(lock_key, tenant_id=tenant_id, plane=TENANT, policy=policy)
            if locked:
                raise AppException("UNAUTHORIZED", f"失败次数过多，账号已锁定 {policy['loginFailLockMinutes']} 分钟")
            if count >= int(policy["captchaAfterFailures"]):
                raise AppException("CAPTCHA_REQUIRED", "账号、学校编码或密码不正确，请输入验证码后继续",
                                   details={"captchaRequired": True, "scene": WX_BIND}, http_status=401)
            raise AppException("UNAUTHORIZED", "账号、学校编码或密码不正确")

        from app.models import WxAccountBinding
        from app.services import audit_log, wx_auth_service
        from app.services.wx_binding_approval_service import (
            assert_school_wx_subject, consume_in_session,
        )
        assert_school_wx_subject(user)
        auth_service_db._ensure_tenant_login_allowed(db, user)
        if not auth_service_db._role_contexts(db, user):
            raise AppException("NO_PERMISSION", "账号尚未分配有效岗位，请联系学校管理员")
        existing = db.scalars(select(WxAccountBinding).where(
            WxAccountBinding.wx_openid == openid,
            WxAccountBinding.tenant_id == user.tenant_id,
        ).with_for_update()).first()
        if existing is not None and existing.is_deleted:
            raise AppException("DATA_CONFLICT", "该微信关联已归档，请联系学校核验处理", http_status=409)
        if existing is not None and existing.user_id != user.id:
            raise AppException("DATA_CONFLICT", "该微信已绑定本校其他账号")
        already_active = existing is not None and str(existing.status or "").upper() == "ACTIVE"
        legacy_same_identity = existing is None and user.wx_openid == openid
        approval_ref = None
        if not (already_active or legacy_same_identity):
            approval_ref = consume_in_session(db, user, openid, binding_approval_token)
        # Reuse the canonical binding writer (including legacy cross-user conflict checks).
        wx_auth_service.bind_openid_in_session(db, openid, user)
        audit_log.record_critical_in_session(
            db, "WX_BINDING_ACTIVATED", f"user:{user.id}", tenant_id=user.tenant_id,
            detail={"approvalRef": approval_ref, "existingIdentity": bool(already_active or legacy_same_identity),
                    "channel": "PASSWORD_WX_BIND"},
        )
        db.commit()
        db.refresh(user)
        _reset_account_risk(lock_key, tenant_id=tenant_id, plane=TENANT)
        return build_login_result(db, user, client_type="MP")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
