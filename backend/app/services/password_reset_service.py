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

_PHONE = re.compile(r"^1[3-9]\d{9}$")
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


def _set(kind: str, identifier: str, payload: dict[str, Any], ttl: int) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    client = get_redis()
    if client is not None:
        try:
            client.set(_prefix(_key(kind, identifier)), raw, ex=max(1, ttl))
            return
        except Exception as exc:  # noqa: BLE001
            if _strict():
                raise _unavailable(exc)
    if _strict():
        raise _unavailable()
    with _LOCK:
        _MEMORY[_key(kind, identifier)] = (time.time() + ttl, raw)


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


def _reset_user_type(client_type: str) -> str:
    """按入口收紧可重置账号类型，避免教师端与学生端身份串用。"""
    return "TEACHER" if client_type in {"TEACHER_PC", "TEACHER_MINI"} else "STUDENT"


def _find_reset_account(login_name: str, tenant_code: str | None, client_type: str):
    from app.models import Tenant, User

    db = get_sessionmaker()()
    try:
        query = select(User).where(
            User.login_name == login_name,
            User.user_type == _reset_user_type(client_type),
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        )
        if tenant_code:
            tenant = db.scalars(select(Tenant).where(
                Tenant.tenant_code == tenant_code,
                Tenant.status.in_(("ACTIVE", "TRIAL", "active", "trial")),
                Tenant.is_deleted.is_(False),
            )).first()
            users = db.scalars(query.where(User.tenant_id == tenant.id).limit(1)).all() if tenant else []
        else:
            users = db.scalars(query.order_by(User.id).limit(2)).all()
        if len(users) != 1:
            return None
        user = users[0]
        phone = decrypt_field(user.phone_encrypted)
        if not phone or not _PHONE.fullmatch(str(phone)):
            return None
        return {
            "userId": int(user.id), "tenantId": int(user.tenant_id),
            "userType": str(user.user_type), "phone": str(phone),
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
                client_type: str = "PC") -> tuple[dict[str, Any], dict[str, Any] | None]:
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
    subject = _digest("subject", f"{tenant_code or '*'}\n{login_name.lower()}")[:32]
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
    candidate = _find_reset_account(login_name, tenant_code, client)
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
    _set("code", request_id, {
        "codeHash": _digest("code", f"{request_id}\n{code}"),
        "userId": candidate["userId"],
        "tenantId": candidate["tenantId"],
        "userType": candidate["userType"],
        "nonceHash": _digest("nonce", nonce),
        "clientType": client,
        "attempts": max(1, int(settings.PASSWORD_RESET_MAX_VERIFY_ATTEMPTS or 5)),
    }, code_ttl)
    try:
        from app.models import PasswordResetSmsJob
        db = get_sessionmaker()()
        try:
            job = PasswordResetSmsJob(
                tenant_id=candidate["tenantId"], request_id=request_id, user_id=candidate["userId"],
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
    if str(settings.APP_ENV or "").lower() == "test" and not _strict():
        public["devCode"] = code
    _uniform_issue_delay(started_at, jitter_ms)
    return public, delivery


def dispatch_code(delivery: dict[str, Any]) -> None:
    """请求后的快速投递；作业已持久化，进程中断时由调度器继续领取。"""
    process_delivery_jobs(limit=1, worker_id="password-reset-inline", job_id=int(delivery["jobId"]))


def process_delivery_jobs(*, limit: int = 20, worker_id: str = "password-reset-scheduler",
                          job_id: int | None = None, tenant_id: int | None = None) -> int:
    """租约领取并投递验证码，at-least-once；同一验证码重复送达仍可安全消费一次。"""
    from sqlalchemy import or_
    from app.models import PasswordResetSmsJob
    from app.services.notification.sms_service import notify_password_reset

    now = _utc_now()
    claimed: list[int] = []
    db = get_sessionmaker()()
    try:
        expired_conditions = [
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
            result = notify_password_reset(row.tenant_id, phone, code)
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
            terminal = attempt >= 3 or row.expires_at <= _utc_now() + timedelta(seconds=20)
            row.last_error = str(result.get("reason") or result.get("status") or "SEND_FAILED")[:500]
            row.locked_by = None; row.lease_expires_at = None
            if terminal:
                row.status = "FAILED"
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


def _verify_code(request_id: str, code: str, nonce: str, client_type: str) -> dict[str, Any] | None:
    expected_code = _digest("code", f"{request_id}\n{code}")
    expected_nonce = _digest("nonce", nonce)
    client = get_redis()
    if client is not None:
        key = _prefix(_key("code", request_id))
        script = """
local raw=redis.call('GET',KEYS[1]); if not raw then return nil end
local p=cjson.decode(raw)
if p.nonceHash~=ARGV[2] or p.clientType~=ARGV[3] then redis.call('DEL',KEYS[1]); return '-1' end
if p.codeHash~=ARGV[1] then
  p.attempts=tonumber(p.attempts or 1)-1
  if p.attempts<=0 then redis.call('DEL',KEYS[1]) else redis.call('SET',KEYS[1],cjson.encode(p),'KEEPTTL') end
  return '0'
end
redis.call('DEL',KEYS[1]); return cjson.encode(p)
"""
        try:
            raw = client.eval(script, 1, key, expected_code, expected_nonce, client_type)
            if not raw or raw in ("0", "-1", b"0", b"-1"):
                return None
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            if _strict():
                raise _unavailable(exc)
    if _strict():
        raise _unavailable()
    memory_key = _key("code", request_id)
    now = time.time()
    with _LOCK:
        item = _MEMORY.get(memory_key)
        if not item or item[0] < now:
            _MEMORY.pop(memory_key, None)
            return None
        payload = json.loads(item[1])
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
    token = secrets.token_urlsafe(32)
    ttl = max(60, min(int(settings.PASSWORD_RESET_TOKEN_TTL_SECONDS or 300), 600))
    _set("token", _digest("token", token), {
        "userId": int(payload["userId"]), "tenantId": int(payload["tenantId"]),
        "userType": str(payload["userType"]),
    }, ttl)
    return {"verified": True, "resetToken": token, "expiresIn": ttl}


def confirm_reset(reset_token: str, new_password: str) -> dict[str, Any]:
    if not _allow(f"confirm-ip:{_ip_hash()}", 30, 5 * 60):
        raise AppException("RATE_LIMITED", "重置尝试过于频繁，请稍后重试", http_status=429)
    from app.services.system_config_service import get_int
    min_len = get_int("SEC_PASSWORD_MIN_LEN", 8)
    if len(new_password or "") < min_len:
        raise AppException("VALIDATION_ERROR", f"新密码长度至少 {min_len} 位")
    token_id = _digest("token", str(reset_token or ""))
    payload = _consume("token", token_id)
    if payload is None:
        raise AppException("RESET_TOKEN_INVALID", "重置凭证无效或已过期，请重新验证", http_status=400)
    from sqlalchemy import delete
    from app.models import AuthRefreshToken, User
    from app.services.auth_service_db import force_subject_revalidation, invalidate_subject_cache
    from app.services.db_service import audit_insert_in_session
    db = get_sessionmaker()()
    committed = False
    try:
        user = db.scalars(select(User).where(
            User.id == int(payload["userId"]), User.tenant_id == int(payload["tenantId"]),
            User.user_type == str(payload["userType"]),
            User.user_type.in_(("STUDENT", "TEACHER")),
            User.status == "ACTIVE", User.is_deleted.is_(False),
        ).with_for_update()).first()
        if user is None:
            raise AppException("RESET_TOKEN_INVALID", "重置凭证无效或已过期，请重新验证", http_status=400)
        if verify_password(new_password, user.password_hash):
            raise AppException("VALIDATION_ERROR", "新密码不能与当前密码相同")
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.version = int(user.version or 0) + 1
        db.execute(delete(AuthRefreshToken).where(AuthRefreshToken.user_id == f"db-{user.id}"))
        # 标记先于数据库提交；即使缓存删除恰逢故障，旧 access 也必须转为查库校验版本。
        force_subject_revalidation(f"db-{user.id}", user.tenant_id)
        audit_insert_in_session(
            db, "PASSWORD_RESET_SELF_SERVICE", "auth",
            {"channel": "SMS", "userType": str(user.user_type)},
            "SUCCESS", tenant_id=user.tenant_id, resource_id=str(user.id),
        )
        db.commit()
        committed = True
        # Access token 每请求复核 permissionVersion；删除缓存后会立即读到已提升的 user.version。
        invalidate_subject_cache(f"db-{user.id}", user.tenant_id)
        return {"success": True, "reloginRequired": True}
    except Exception:
        db.rollback()
        if not committed:
            # 数据库瞬时失败或新密码与旧密码相同，不让用户重新走一遍短信验证。
            _set("token", token_id, payload, 60)
        raise
    finally:
        db.close()


def reset_for_tests() -> None:
    with _LOCK:
        _MEMORY.clear()
        _LIMITS.clear()
