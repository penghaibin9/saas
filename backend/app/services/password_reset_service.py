"""学生与教师短信找回密码。

安全边界：只使用账号已绑定手机号；响应不暴露账号/手机号是否存在；验证码和重置令牌
只保存 HMAC；生产/预发强制 Redis；成功重置后撤销 refresh 并提升账号版本。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.context import get_request_meta
from app.core.exceptions import AppException
from app.core.field_crypto import decrypt_field, encrypt_field
from app.core.redis_client import _prefix, get_redis
from app.core.security import hash_password, verify_password
from app.db.session import db_enabled, get_sessionmaker

_PHONE = re.compile(r"^1[3-9][0-9]{9}$")
_MEMORY: dict[str, tuple[float, str]] = {}
_LIMITS: dict[str, tuple[float, int]] = {}
_LOCK = threading.Lock()
_LOG = logging.getLogger("app.password_reset")


def _strict() -> bool:
    return settings.is_prod or str(settings.APP_ENV or "").lower() == "staging"


def _utc_now() -> datetime:
    from app.core.timeutil import utc_now_naive
    return utc_now_naive()


def _unavailable(exc: Exception | None = None) -> AppException:
    error = AppException("AUTH_STORE_UNAVAILABLE", "密码重置服务暂时不可用，请稍后重试", http_status=503)
    if exc is not None:
        error.__cause__ = exc
    return error


def _secret() -> bytes:
    return (settings.JWT_SECRET_KEY or settings.JWT_SECRET).encode("utf-8")


def _digest(scope: str, value: str) -> str:
    return hmac.new(_secret(), f"{scope}\n{value}".encode("utf-8"), hashlib.sha256).hexdigest()


def _ip_hash() -> str:
    ip = str((get_request_meta() or {}).get("ip") or "unknown")
    return _digest("ip", ip)[:24]


def _key(kind: str, identifier: str) -> str:
    return f"auth:password-reset:{kind}:{identifier}"


def _set(kind: str, identifier: str, payload: dict[str, Any], ttl: int, *, require_shared: bool = False) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    client = get_redis()
    if client is not None:
        try:
            client.set(_prefix(_key(kind, identifier)), raw, ex=max(1, ttl))
            return
        except Exception as exc:  # noqa: BLE001
            if _strict() or require_shared:
                raise _unavailable(exc)
    if _strict() or require_shared:
        raise _unavailable()
    with _LOCK:
        _MEMORY[_key(kind, identifier)] = (time.time() + ttl, raw)


def _read(kind: str, identifier: str, *, require_shared: bool = False) -> dict | None:
    """Read a proof without consuming it; durable business receipts arbitrate final use."""
    client = get_redis()
    if client is not None:
        try:
            raw = client.get(_prefix(_key(kind, identifier)))
            return json.loads(raw) if raw else None
        except Exception as exc:
            if _strict() or require_shared:
                raise _unavailable(exc)
    if _strict() or require_shared:
        raise _unavailable()
    with _LOCK:
        item = _MEMORY.get(_key(kind, identifier))
        return json.loads(item[1]) if item and item[0] > time.time() else None


def _delete(kind: str, identifier: str) -> None:
    client = get_redis()
    if client is not None:
        try:
            client.delete(_prefix(_key(kind, identifier)))
            return
        except Exception as exc:  # noqa: BLE001
            if _strict():
                raise _unavailable(exc)
    if _strict():
        raise _unavailable()
    with _LOCK:
        _MEMORY.pop(_key(kind, identifier), None)


def _consume(kind: str, identifier: str) -> dict[str, Any] | None:
    client = get_redis()
    if client is not None:
        key = _prefix(_key(kind, identifier))
        try:
            try:
                raw = client.execute_command("GETDEL", key)
            except Exception:
                raw = client.eval(
                    "local v=redis.call('GET',KEYS[1]); if v then redis.call('DEL',KEYS[1]) end; return v",
                    1, key,
                )
            return json.loads(raw) if raw else None
        except Exception as exc:  # noqa: BLE001
            if _strict():
                raise _unavailable(exc)
    if _strict():
        raise _unavailable()
    with _LOCK:
        item = _MEMORY.pop(_key(kind, identifier), None)
    if not item or item[0] < time.time():
        return None
    return json.loads(item[1])


def _allow(label: str, limit: int, window: int) -> bool:
    """Redis 固定窗原子限流；开发/测试才允许进程内回落。"""
    client = get_redis()
    store_key = _prefix(_key("rate", label))
    if client is not None:
        try:
            count = int(client.incr(store_key))
            if count == 1:
                client.expire(store_key, window)
            return count <= limit
        except Exception as exc:  # noqa: BLE001
            if _strict():
                raise _unavailable(exc)
    if _strict():
        raise _unavailable()
    now = time.time()
    with _LOCK:
        expires, count = _LIMITS.get(label, (now + window, 0))
        if expires <= now:
            expires, count = now + window, 0
        count += 1
        _LIMITS[label] = (expires, count)
        return count <= limit


def _reset_user_types(client_type: str) -> tuple[str, ...]:
    """按入口收紧可重置账号类型，避免教师端与学生端身份串用。"""
    if client_type in {"TEACHER_PC", "TEACHER_MINI"}:
        return ('TEACHER', 'STAFF', 'ADMIN', 'SCHOOL_ADMIN')
    return ('STUDENT',) if client_type in {'PC', 'STUDENT_PC', 'STUDENT_MINI'} else ()


def requires_independent_phone_verification(db, user, binding):
    """All current roles and known recovery risk; never just the selected low role."""
    from app.services import auth_service_db, control_plane_auth_service as auth
    from app.core.permissions import get_effective_permission_patterns
    if binding and binding.recovery_frozen:
        return True
    auth_service_db._ensure_tenant_login_allowed(db, user)
    contexts = auth_service_db._role_contexts(db, user)
    if not contexts or user.user_type in {'ADMIN', 'SCHOOL_ADMIN'}:
        return True
    for context in contexts:
        code = context['roleCode']
        if any(word in code for word in ('ADMIN', 'SECURITY', 'OPERATOR', 'PLATFORM')):
            return True
        from app.core.context import get_tenant, set_tenant
        previous_tenant = get_tenant()
        try:
            set_tenant(user.tenant_id)
            patterns = get_effective_permission_patterns({'userId': f'db-{user.id}', 'tenantId': user.tenant_id,
                'loginName': user.login_name, 'userType': user.user_type, 'currentRoleCode': code,
                'activeContextId': context['contextId']}, strict=True)
        finally:
            set_tenant(previous_tenant)
        if any(p == '*' or p.startswith(('system.', 'systemAdmin.', 'platform.', 'security.'))
               and not p.endswith(('.view', '.list')) for p in patterns):
            return True
    return bool(auth._remaining_lock(auth._subject_risk_key(None, user.login_name, user), tenant_id=user.tenant_id, plane=auth.TENANT))


def _recovery_allowed(db, user, binding):
    from app.services.phone_login_service import phone_policy_enabled
    if not binding or binding.is_deleted or binding.state != 'VERIFIED' or binding.recovery_frozen:
        return False
    if not phone_policy_enabled(db, user.tenant_id, 'SEC_PHONE_RECOVERY_ENABLED') or user.must_change_password:
        return False
    return not requires_independent_phone_verification(db, user, binding)


def _reset_invalid():
    return AppException('RESET_TOKEN_INVALID', '重置凭证无效或已过期，请重新验证', http_status=400)


def _snapshot_user(db, payload):
    from app.models import User, PhoneLoginBinding
    if payload.get('purpose') != 'RESET_PASSWORD' or payload.get('expiresAt', 0) <= time.time():
        raise _reset_invalid()
    user = db.scalar(select(User).where(User.id == payload['userId'], User.tenant_id == payload['tenantId'],
        User.is_deleted.is_(False), User.status == 'ACTIVE').with_for_update())
    binding = db.scalar(select(PhoneLoginBinding).where(PhoneLoginBinding.user_id == payload['userId'],
        PhoneLoginBinding.tenant_id == payload['tenantId']).with_for_update())
    if not user or user.user_type != payload['userType'] or not _recovery_allowed(db, user, binding):
        raise _reset_invalid()
    if (int(user.credential_version) != payload['credentialVersion'] or int(binding.version) != payload['bindingVersion']
            or binding.active_phone_lookup != payload['phoneLookup']):
        raise _reset_invalid()
    return user


def _find_reset_account(login_name: str, tenant_code: str | None, client_type: str, identifier_type: str = 'ACCOUNT'):
    from app.models import PhoneLoginBinding, Tenant, User

    db = get_sessionmaker()()
    try:
        query = select(User).where(
            User.user_type.in_(_reset_user_types(client_type)),
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        )
        if identifier_type == 'ACCOUNT':
            query = query.where(User.login_name == login_name)
        elif identifier_type != 'PHONE' or not tenant_code:
            return None
        if tenant_code:
            tenant = db.scalars(select(Tenant).where(
                Tenant.tenant_code == tenant_code,
                Tenant.status.in_(("ACTIVE", "TRIAL", "active", "trial")),
                Tenant.is_deleted.is_(False),
            )).first()
            if tenant and identifier_type == 'PHONE':
                from app.services.phone_login_service import phone_lookup
                query = query.join(PhoneLoginBinding, (PhoneLoginBinding.user_id == User.id) &
                    (PhoneLoginBinding.tenant_id == User.tenant_id)).where(
                    PhoneLoginBinding.state == 'VERIFIED', PhoneLoginBinding.is_deleted.is_(False),
                    PhoneLoginBinding.active_phone_lookup == phone_lookup(tenant.id, login_name))
            users = db.scalars(query.where(User.tenant_id == tenant.id).limit(1)).all() if tenant else []
        else:
            users = db.scalars(query.order_by(User.id).limit(2)).all()
        if len(users) != 1:
            return None
        user = users[0]
        binding = db.scalars(select(PhoneLoginBinding).where(
            PhoneLoginBinding.tenant_id == user.tenant_id, PhoneLoginBinding.user_id == user.id,
            PhoneLoginBinding.state == "VERIFIED", PhoneLoginBinding.is_deleted.is_(False),
        )).first()
        if not _recovery_allowed(db, user, binding):
            return None
        phone = decrypt_field(binding.phone_ciphertext, allow_legacy_plaintext=False)
        if not phone or not _PHONE.fullmatch(str(phone).removeprefix("+86")):
            return None
        return {
            "userId": int(user.id), "tenantId": int(user.tenant_id),
            "userType": str(user.user_type), "phone": str(phone).removeprefix("+86"),
            "credentialVersion": int(user.credential_version), "bindingVersion": int(binding.version),
            "phoneLookup": binding.active_phone_lookup,
        }
    finally:
        db.close()


def _assert_queue_ready() -> None:
    """在账号查询前检查队列表；迁移遗漏时所有账号得到同一 503，避免存在性侧信道。"""
    from app.models import PasswordResetSmsJob
    db = get_sessionmaker()()
    try:
        db.scalar(select(PasswordResetSmsJob.id).limit(1))
    except Exception as exc:
        raise AppException("SMS_QUEUE_UNAVAILABLE", "短信发送队列暂时不可用，请稍后重试", http_status=503) from exc
    finally:
        db.close()


def _uniform_issue_delay(started_at: float, jitter_ms: int) -> None:
    remaining = started_at + 0.18 + (jitter_ms / 1000) - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)


def begin_reset(login_name: str, tenant_code: str | None, client_nonce: str,
                client_type: str = "PC", *, identifier_type: str = 'ACCOUNT') -> tuple[dict[str, Any], dict[str, Any] | None]:
    """创建挑战，返回统一公开响应和仅供后台发送使用的临时投递参数。"""
    if not db_enabled():
        raise AppException("AUTH_STORE_UNAVAILABLE", "密码重置服务暂时不可用", http_status=503)
    from app.services.notification.sms_service import password_reset_ready
    if not password_reset_ready():
        raise AppException("SMS_UNAVAILABLE", "短信服务暂时不可用，请稍后重试；仍无法处理时再联系学校管理员",
                           http_status=503)
    _assert_queue_ready()
    started_at = time.monotonic()
    jitter_ms = secrets.randbelow(51)
    login_name = str(login_name or "").strip()
    tenant_code = str(tenant_code or "").strip() or None
    nonce = str(client_nonce or "").strip()
    client = str(client_type or "PC").strip().upper()
    if identifier_type == 'PHONE':
        from app.services.phone_login_service import require_phone_identifier
        login_name = require_phone_identifier(tenant_code, login_name)
    elif identifier_type != 'ACCOUNT':
        raise _reset_invalid()
    subject = _digest("subject", f"{tenant_code or '*'}\n{identifier_type}\n{login_name.lower()}")[:32]
    resend_window = max(30, int(settings.PASSWORD_RESET_RESEND_SECONDS or 60))
    if (not _allow(f"cooldown:{subject}", 1, resend_window)
            or not _allow(f"issue-account:{subject}", 3, 15 * 60)
            or not _allow(f"issue-ip:{_ip_hash()}", 20, 15 * 60)):
        raise AppException("RATE_LIMITED", "验证码请求过于频繁，请稍后重试", http_status=429)

    request_id = "pr_" + secrets.token_urlsafe(24)
    code_ttl = max(60, min(int(settings.PASSWORD_RESET_CODE_TTL_SECONDS or 300), 600))
    public = {
        "accepted": True,
        "requestId": request_id,
        "expiresIn": code_ttl,
        "retryAfter": resend_window,
    }
    candidate = _find_reset_account(login_name, tenant_code, client, identifier_type)
    if candidate is None:
        _uniform_issue_delay(started_at, jitter_ms)
        return public, None
    # 同一手机号可能历史上关联多个账号；小时上限静默降级为统一受理响应，避免通过
    # 限流差异反查某账号是否存在。
    phone_key = _digest("phone", candidate["phone"])[:32]
    if not _allow(f"issue-phone:{phone_key}", 5, 60 * 60):
        _uniform_issue_delay(started_at, jitter_ms)
        return public, None

    code = f"{secrets.randbelow(1_000_000):06d}"
    snapshot = {
        'purpose': 'RESET_PASSWORD', 'operationId': request_id, 'expiresAt': int(time.time()) + code_ttl,
        'credentialVersion': candidate['credentialVersion'], 'bindingVersion': candidate['bindingVersion'],
        'phoneLookup': candidate['phoneLookup'],
        "codeHash": _digest("code", f"{request_id}\n{code}"),
        "userId": candidate["userId"],
        "tenantId": candidate["tenantId"],
        "userType": candidate["userType"],
        "nonceHash": _digest("nonce", nonce),
        "clientType": client,
        "attempts": max(1, int(settings.PASSWORD_RESET_MAX_VERIFY_ATTEMPTS or 5)),
    }
    _set("code", request_id, snapshot, code_ttl)
    _set("reset-operation", request_id, snapshot, code_ttl)
    try:
        from app.models import PasswordResetSmsJob
        db = get_sessionmaker()()
        try:
            job = PasswordResetSmsJob(
                tenant_id=candidate["tenantId"], request_id=request_id, user_id=candidate["userId"],
                purpose='RESET_PASSWORD', challenge_ref=request_id,
                phone_encrypted=encrypt_field(candidate["phone"]), code_encrypted=encrypt_field(code),
                expires_at=_utc_now() + timedelta(seconds=code_ttl), status="PENDING", created_by=0,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = int(job.id)
        finally:
            db.close()
    except Exception as exc:  # reliable delivery acceptance must be durable before returning success
        _delete("code", request_id)
        raise AppException("SMS_QUEUE_UNAVAILABLE", "短信发送队列暂时不可用，请稍后重试", http_status=503) from exc
    delivery = {"jobId": job_id}
    _uniform_issue_delay(started_at, jitter_ms)
    return public, delivery


def dispatch_code(delivery: dict[str, Any]) -> None:
    """请求后的快速投递；作业已持久化，进程中断时由调度器继续领取。"""
    process_delivery_jobs(limit=1, worker_id="password-reset-inline", job_id=int(delivery["jobId"]))


def process_delivery_jobs(*, limit: int = 20, worker_id: str = "password-reset-scheduler",
                          job_id: int | None = None, tenant_id: int | None = None,
                          purposes: tuple[str, ...] = ("RESET_PASSWORD",)) -> int:
    """租约领取并投递验证码，at-least-once；同一验证码重复送达仍可安全消费一次。"""
    from sqlalchemy import or_
    from app.models import PasswordResetSmsJob
    from app.services.notification.sms_service import notify_password_reset
    if not purposes or set(purposes) - {"RESET_PASSWORD", "BIND_PHONE", "CHANGE_PHONE"}:
        raise ValueError("Unsupported SMS purpose")

    now = _utc_now()
    claimed: list[int] = []
    db = get_sessionmaker()()
    try:
        expired_conditions = [
            PasswordResetSmsJob.purpose.in_(purposes),
            PasswordResetSmsJob.is_deleted.is_(False),
            PasswordResetSmsJob.status.in_(("PENDING", "RETRY_WAIT", "PROCESSING")),
            PasswordResetSmsJob.expires_at <= now,
        ]
        if tenant_id is not None:
            expired_conditions.append(PasswordResetSmsJob.tenant_id == int(tenant_id))
        expired_rows = db.scalars(select(PasswordResetSmsJob).where(*expired_conditions)
                                  .with_for_update(skip_locked=True).limit(100)).all()
        for expired in expired_rows:
            expired.status = "EXPIRED"
            expired.phone_encrypted = None; expired.code_encrypted = None
            expired.locked_by = None; expired.lease_expires_at = None
            expired.version = int(expired.version or 0) + 1
        conditions = [
            PasswordResetSmsJob.purpose.in_(purposes),
            PasswordResetSmsJob.is_deleted.is_(False),
            PasswordResetSmsJob.status.in_(("PENDING", "RETRY_WAIT", "PROCESSING")),
            PasswordResetSmsJob.expires_at > now,
            or_(PasswordResetSmsJob.next_retry_at.is_(None), PasswordResetSmsJob.next_retry_at <= now),
            or_(PasswordResetSmsJob.status != "PROCESSING",
                PasswordResetSmsJob.lease_expires_at.is_(None),
                PasswordResetSmsJob.lease_expires_at <= now),
        ]
        if job_id is not None:
            conditions.append(PasswordResetSmsJob.id == int(job_id))
        if tenant_id is not None:
            conditions.append(PasswordResetSmsJob.tenant_id == int(tenant_id))
        rows = db.scalars(select(PasswordResetSmsJob).where(*conditions)
                          .order_by(PasswordResetSmsJob.id).with_for_update(skip_locked=True)
                          .limit(max(1, min(int(limit or 1), 100)))).all()
        for row in rows:
            row.status = "PROCESSING"
            row.locked_by = worker_id[:100]
            row.lease_expires_at = now + timedelta(seconds=30)
            row.attempt_count = int(row.attempt_count or 0) + 1
            row.version = int(row.version or 0) + 1
            claimed.append(int(row.id))
        db.commit()
    finally:
        db.close()

    sent = 0
    for claimed_id in claimed:
        db = get_sessionmaker()()
        try:
            row = db.get(PasswordResetSmsJob, claimed_id)
            if row is None or row.status != "PROCESSING" or row.locked_by != worker_id:
                continue
            if row.expires_at <= _utc_now() or not row.phone_encrypted or not row.code_encrypted:
                row.status = "EXPIRED"
                row.phone_encrypted = None; row.code_encrypted = None
                row.locked_by = None; row.lease_expires_at = None
                db.commit()
                _delete("code", row.request_id)
                continue
            phone = decrypt_field(row.phone_encrypted, allow_legacy_plaintext=False)
            code = decrypt_field(row.code_encrypted, allow_legacy_plaintext=False)
            if row.purpose == "RESET_PASSWORD":
                snapshot = _read('reset-operation', row.request_id)
                try:
                    if not snapshot:
                        raise _reset_invalid()
                    _snapshot_user(db, snapshot)
                except AppException as exc:
                    if exc.http_status >= 500:
                        raise
                    row.status = 'EXPIRED'
                    row.phone_encrypted = row.code_encrypted = None
                    row.locked_by = row.lease_expires_at = None
                    db.commit()
                    continue
                result = notify_password_reset(row.tenant_id, phone, code)
            else:
                from app.services.phone_binding_service import delivery_is_current
                from app.services.notification.sms_service import notify_phone_verification
                if not delivery_is_current(db, row):
                    row.status = "EXPIRED"
                    row.phone_encrypted = row.code_encrypted = None
                    row.locked_by = row.lease_expires_at = None
                    db.commit()
                    continue
                result = notify_phone_verification(row.tenant_id, phone, code, row.purpose)
            if result.get("status") == "SENT":
                row.status = "SENT"
                row.provider_request_id = str(result.get("requestId") or "")[:100] or None
                row.last_error = None
                row.phone_encrypted = None; row.code_encrypted = None
                row.locked_by = None; row.lease_expires_at = None
                row.version = int(row.version or 0) + 1
                db.commit()
                sent += 1
                continue
            attempt = int(row.attempt_count or 1)
            terminal = (result.get("retryable") is False or attempt >= 3
                        or row.expires_at <= _utc_now() + timedelta(seconds=20))
            row.last_error = str(result.get("reason") or result.get("status") or "SEND_FAILED")[:500]
            row.locked_by = None; row.lease_expires_at = None
            if terminal:
                row.status = "FAILED"
                row.next_retry_at = None
                row.phone_encrypted = None; row.code_encrypted = None
            else:
                row.status = "RETRY_WAIT"
                row.next_retry_at = _utc_now() + timedelta(seconds=10 * (2 ** (attempt - 1)))
            row.version = int(row.version or 0) + 1
            db.commit()
            if terminal:
                _delete("code", row.request_id)
        except Exception as exc:  # keep lease recoverable; scheduler will reclaim it
            db.rollback()
            _LOG.exception("password_reset_delivery_failed job=%s error=%s", claimed_id, type(exc).__name__)
        finally:
            db.close()
    return sent


def _verify_code(request_id: str, code: str, nonce: str, client_type: str,
                 *, purpose: str = "RESET_PASSWORD", require_shared: bool = False) -> dict[str, Any] | None:
    expected_code = _digest("code", f"{request_id}\n{code}")
    expected_nonce = _digest("nonce", nonce)
    client = get_redis()
    if client is not None:
        key = _prefix(_key("code", request_id))
        script = """
local raw=redis.call('GET',KEYS[1]); if not raw then return nil end
local p=cjson.decode(raw)
if (p.purpose or 'RESET_PASSWORD')~=ARGV[4] then return nil end
if p.nonceHash~=ARGV[2] or p.clientType~=ARGV[3] then redis.call('DEL',KEYS[1]); return '-1' end
if p.codeHash~=ARGV[1] then
  p.attempts=tonumber(p.attempts or 1)-1
  if p.attempts<=0 then redis.call('DEL',KEYS[1]) else redis.call('SET',KEYS[1],cjson.encode(p),'KEEPTTL') end
  return '0'
end
redis.call('DEL',KEYS[1]); return cjson.encode(p)
"""
        try:
            raw = client.eval(script, 1, key, expected_code, expected_nonce, client_type, purpose)
            if not raw or raw in ("0", "-1", b"0", b"-1"):
                return None
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            if _strict() or require_shared:
                raise _unavailable(exc)
    if _strict() or require_shared:
        raise _unavailable()
    memory_key = _key("code", request_id)
    now = time.time()
    with _LOCK:
        item = _MEMORY.get(memory_key)
        if not item or item[0] < now:
            _MEMORY.pop(memory_key, None)
            return None
        payload = json.loads(item[1])
        if payload.get("purpose", "RESET_PASSWORD") != purpose:
            return None
        if (not hmac.compare_digest(str(payload.get("nonceHash") or ""), expected_nonce)
                or not hmac.compare_digest(str(payload.get("clientType") or ""), client_type)):
            _MEMORY.pop(memory_key, None)
            return None
        if not hmac.compare_digest(str(payload.get("codeHash") or ""), expected_code):
            payload["attempts"] = int(payload.get("attempts") or 1) - 1
            if payload["attempts"] <= 0:
                _MEMORY.pop(memory_key, None)
            else:
                _MEMORY[memory_key] = (item[0], json.dumps(payload, separators=(",", ":")))
            return None
        _MEMORY.pop(memory_key, None)
        return payload


def verify_reset_code(request_id: str, code: str, client_nonce: str,
                      client_type: str = "PC") -> dict[str, Any]:
    if not _allow(f"verify-ip:{_ip_hash()}", 60, 5 * 60):
        raise AppException("RATE_LIMITED", "验证尝试过于频繁，请稍后重试", http_status=429)
    payload = _verify_code(str(request_id or ""), str(code or "").strip(),
                           str(client_nonce or "").strip(), str(client_type or "PC").strip().upper())
    if payload is None:
        raise AppException("RESET_CODE_INVALID", "验证码无效或已过期，请重新获取", http_status=400)
    with get_sessionmaker()() as db:
        _snapshot_user(db, payload)
    token = secrets.token_urlsafe(32)
    ttl = min(int(payload['expiresAt']) - int(time.time()), int(settings.PASSWORD_RESET_TOKEN_TTL_SECONDS or 300))
    if ttl <= 0:
        raise _reset_invalid()
    _set("token", _digest("token", token), payload, ttl)
    return {"verified": True, "resetToken": token, "expiresIn": ttl}


def confirm_reset(reset_token: str, new_password: str) -> dict[str, Any]:
    if not _allow(f"confirm-ip:{_ip_hash()}", 30, 5 * 60):
        raise AppException("RATE_LIMITED", "重置尝试过于频繁，请稍后重试", http_status=429)
    token_id = _digest("token", str(reset_token or ""))
    payload = _read("token", token_id)
    if payload is None:
        raise AppException("RESET_TOKEN_INVALID", "重置凭证无效或已过期，请重新验证", http_status=400)
    from app.services.control_plane_auth_service import resolve_login_policy, TENANT
    min_len = int(resolve_login_policy(tenant_id=int(payload['tenantId']), principal_plane=TENANT)['passwordMinLength'])
    if len(new_password or '') < min_len:
        raise AppException('VALIDATION_ERROR', f'新密码长度至少 {min_len} 位')
    from app.models import IdempotencyRecord, User
    from app.services.auth_service_db import credential_change_receipt
    from app.services.db_service import audit_insert_in_session
    db = get_sessionmaker()()
    try:
        # Lock original subject first; the same unique durable record arbitrates all retries.
        user = db.scalar(select(User).where(User.id == payload['userId'], User.tenant_id == payload['tenantId']).with_for_update())
        if not user or payload.get('expiresAt', 0) <= time.time():
            raise _reset_invalid()
        fingerprint = _digest('reset-password-request', new_password)
        receipt = db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.tenant_id == user.tenant_id,
            IdempotencyRecord.user_id == str(user.id), IdempotencyRecord.operation == 'PASSWORD_RESET',
            IdempotencyRecord.key_hash == token_id).with_for_update())
        if receipt:
            if not hmac.compare_digest(receipt.fingerprint, fingerprint):
                raise _reset_invalid()
            return dict(receipt.result_json)
        user = _snapshot_user(db, payload)
        if verify_password(new_password, user.password_hash):
            raise AppException("VALIDATION_ERROR", "新密码不能与当前密码相同")
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.version = int(user.version or 0) + 1
        user.credential_version = int(getattr(user, "credential_version", 0) or 0) + 1
        audit_insert_in_session(
            db, "PASSWORD_RESET_SELF_SERVICE", "auth",
            {"channel": "SMS", "userType": str(user.user_type)},
            "SUCCESS", tenant_id=user.tenant_id, resource_id=str(user.id),
        )
        result = {'success': True, 'reloginRequired': True, 'runtimeMaterialized': True,
            'operationId': payload['operationId'], 'credentialVersion': user.credential_version,
            'cacheInvalidated': False, 'cacheRecoveryRequired': True, 'notificationQueued': True}
        db.add(IdempotencyRecord(tenant_id=user.tenant_id, user_id=str(user.id), operation='PASSWORD_RESET',
            key_hash=token_id, fingerprint=fingerprint, state='SUCCEEDED', result_json=result,
            expires_at=_utc_now() + timedelta(days=1)))
        from app.services.message_event_outbox_service import emit_message_event
        emit_message_event(db, event_code='AUTH.PASSWORD_RESET', source_module='systemAdmin', source_biz_type='USER',
            source_biz_id=user.id, recipient_refs=[{'userId': user.id}], tenant_id=user.tenant_id,
            content='您的登录密码已重置。如非本人操作，请立即联系学校核对。', dedup_key=payload['operationId'])
        db.commit()
        return {**result, **credential_change_receipt(user, {'userId': f'db-{user.id}', 'tenantId': user.tenant_id})}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def reset_operation_status(reset_token: str, client_nonce: str) -> dict[str, Any]:
    """Read only the original proof's receipt; never consumes or reapplies a reset."""
    if not _allow(f'reset-status-ip:{_ip_hash()}', 60, 5 * 60):
        raise AppException('RATE_LIMITED', '查询过于频繁，请稍后重试', http_status=429)
    token_id = _digest('token', reset_token)
    payload = _read('token', token_id)
    if not payload or not hmac.compare_digest(payload['nonceHash'], _digest('nonce', client_nonce)):
        raise _reset_invalid()
    from app.models import IdempotencyRecord
    with get_sessionmaker()() as db:
        receipt = db.scalar(select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == payload['tenantId'], IdempotencyRecord.user_id == str(payload['userId']),
            IdempotencyRecord.operation == 'PASSWORD_RESET', IdempotencyRecord.key_hash == token_id))
        if receipt:
            return dict(receipt.result_json)
    return {'runtimeMaterialized': False, 'state': 'PENDING'}


def reset_for_tests() -> None:
    with _LOCK:
        _MEMORY.clear()
        _LIMITS.clear()
