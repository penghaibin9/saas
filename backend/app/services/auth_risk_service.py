"""Distributed authentication-risk authority.

Production authentication must never degrade to per-process memory.  Login
failure/lock state is MySQL-authoritative so Redis outages, worker changes and
process restarts cannot reset the security decision.  Redis may still be used by
compatibility callers as a cache/fast-path, but a missing cache value never means
"not locked" without checking this authority.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker

LOGIN_ACCOUNT = "LOGIN_ACCOUNT"
LOGIN_ACCOUNT_IP = "LOGIN_ACCOUNT_IP"
LOGIN_IP = "LOGIN_IP"
PLATFORM_ACCOUNT = "PLATFORM_ACCOUNT"
PLATFORM_ACCOUNT_IP = "PLATFORM_ACCOUNT_IP"
PLATFORM_IP = "PLATFORM_IP"
RATE_LIMIT = "RATE_LIMIT"


def strict_env() -> bool:
    app_env = str(settings.APP_ENV or "").strip().lower()
    deploy = str(settings.DEPLOYMENT_MODE or "").strip().lower()
    return bool(getattr(settings, "is_prod", False)) or app_env in {"production", "staging"} or deploy in {"production", "staging"}


def _store_unavailable(message: str = "认证风控存储暂时不可用") -> AppException:
    return AppException("AUTH_RISK_STORE_UNAVAILABLE", message, http_status=503)


def _key_hash(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _session(*, required: bool = True):
    if not db_enabled():
        if required or strict_env():
            raise _store_unavailable("认证风控需要数据库持久化")
        return None
    try:
        return get_sessionmaker()()
    except Exception as exc:  # noqa: BLE001
        if required or strict_env():
            raise _store_unavailable() from exc
        return None


def _remaining(locked_until: datetime | None, now: datetime) -> int:
    if locked_until is None or locked_until <= now:
        return 0
    return max(1, int((locked_until - now).total_seconds()))


def login_locked(key: str, *, risk_type: str = LOGIN_ACCOUNT, tenant_id: int | None = None) -> int | None:
    """Return lock seconds; ``None`` only in non-strict DB-disabled development."""
    db = _session(required=strict_env())
    if db is None:
        return None
    try:
        from app.models.auth_risk import AuthRiskState

        now = datetime.utcnow()
        row = db.scalars(select(AuthRiskState).where(
            AuthRiskState.risk_type == risk_type,
            AuthRiskState.risk_key_hash == _key_hash(key),
            AuthRiskState.is_deleted.is_(False),
        )).first()
        if row is None:
            return 0
        if row.expires_at is not None and row.expires_at <= now and _remaining(row.locked_until, now) == 0:
            return 0
        return _remaining(row.locked_until, now)
    except AppException:
        raise
    except Exception as exc:  # noqa: BLE001
        if strict_env() or db_enabled():
            raise _store_unavailable() from exc
        return None
    finally:
        db.close()


def failure_count(key: str, *, risk_type: str = LOGIN_ACCOUNT, tenant_id: int | None = None) -> int | None:
    db = _session(required=strict_env())
    if db is None:
        return None
    try:
        from app.models.auth_risk import AuthRiskState

        now = datetime.utcnow()
        row = db.scalars(select(AuthRiskState).where(
            AuthRiskState.risk_type == risk_type,
            AuthRiskState.risk_key_hash == _key_hash(key),
            AuthRiskState.is_deleted.is_(False),
        )).first()
        if row is None or (row.expires_at is not None and row.expires_at <= now and _remaining(row.locked_until, now) == 0):
            return 0
        return max(0, int(row.failure_count or 0))
    except Exception as exc:  # noqa: BLE001
        if strict_env() or db_enabled():
            raise _store_unavailable() from exc
        return None
    finally:
        db.close()


def record_failure(
    key: str,
    *,
    threshold: int,
    lock_seconds: int,
    risk_type: str = LOGIN_ACCOUNT,
    tenant_id: int | None = None,
) -> tuple[int, int] | None:
    """Atomically increment a security bucket and lock at ``threshold``.

    The absent-row race is retried after the unique-key winner commits.  MySQL
    row locking then serializes subsequent increments, preventing lost updates
    across workers.
    """
    limit = max(1, int(threshold))
    lock_for = max(1, int(lock_seconds))
    digest = _key_hash(key)
    for attempt in range(3):
        db = _session(required=strict_env())
        if db is None:
            return None
        try:
            from app.models.auth_risk import AuthRiskState

            now = datetime.utcnow()
            row = db.scalars(select(AuthRiskState).where(
                AuthRiskState.risk_type == risk_type,
                AuthRiskState.risk_key_hash == digest,
                AuthRiskState.is_deleted.is_(False),
            ).with_for_update()).first()
            if row is None:
                row = AuthRiskState(
                    risk_type=risk_type,
                    risk_key_hash=digest,
                    tenant_id=int(tenant_id) if tenant_id is not None else None,
                    failure_count=0,
                    window_started_at=now,
                    expires_at=now + timedelta(seconds=lock_for),
                )
                db.add(row)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    if attempt < 2:
                        continue
                    raise
            if row.expires_at is not None and row.expires_at <= now and _remaining(row.locked_until, now) == 0:
                row.failure_count = 0
                row.window_started_at = now
                row.locked_until = None
            row.tenant_id = int(tenant_id) if tenant_id is not None else row.tenant_id
            row.failure_count = int(row.failure_count or 0) + 1
            row.expires_at = now + timedelta(seconds=lock_for)
            if row.failure_count >= limit:
                row.locked_until = now + timedelta(seconds=lock_for)
            row.version = int(row.version or 0) + 1
            db.commit()
            return int(row.failure_count), _remaining(row.locked_until, now)
        except IntegrityError:
            try:
                db.rollback()
            except Exception:
                pass
            if attempt < 2:
                continue
            if strict_env() or db_enabled():
                raise _store_unavailable() from None
            return None
        except AppException:
            raise
        except Exception as exc:  # noqa: BLE001
            try:
                db.rollback()
            except Exception:
                pass
            if strict_env() or db_enabled():
                raise _store_unavailable() from exc
            return None
        finally:
            db.close()
    raise _store_unavailable()


def reset_failure(key: str, *, risk_type: str = LOGIN_ACCOUNT, tenant_id: int | None = None) -> bool:
    db = _session(required=strict_env())
    if db is None:
        return False
    try:
        from app.models.auth_risk import AuthRiskState

        db.execute(delete(AuthRiskState).where(
            AuthRiskState.risk_type == risk_type,
            AuthRiskState.risk_key_hash == _key_hash(key),
        ))
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        if strict_env() or db_enabled():
            raise _store_unavailable() from exc
        return False
    finally:
        db.close()


def fixed_window_allow(bucket: str, limit: int, window_seconds: int) -> bool | None:
    """MySQL fallback for Redis rate limiting; never process-local in strict env."""
    cap = max(1, int(limit))
    window = max(1, int(window_seconds))
    digest = _key_hash(bucket)
    for attempt in range(3):
        db = _session(required=strict_env())
        if db is None:
            return None
        try:
            from app.models.auth_risk import AuthRiskState

            now = datetime.utcnow()
            row = db.scalars(select(AuthRiskState).where(
                AuthRiskState.risk_type == RATE_LIMIT,
                AuthRiskState.risk_key_hash == digest,
                AuthRiskState.is_deleted.is_(False),
            ).with_for_update()).first()
            if row is None:
                row = AuthRiskState(
                    risk_type=RATE_LIMIT,
                    risk_key_hash=digest,
                    failure_count=0,
                    window_started_at=now,
                    expires_at=now + timedelta(seconds=window),
                )
                db.add(row)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    if attempt < 2:
                        continue
                    raise
            if row.expires_at is None or row.expires_at <= now:
                row.failure_count = 0
                row.window_started_at = now
                row.expires_at = now + timedelta(seconds=window)
            if int(row.failure_count or 0) >= cap:
                db.commit()
                return False
            row.failure_count = int(row.failure_count or 0) + 1
            row.version = int(row.version or 0) + 1
            db.commit()
            return True
        except IntegrityError:
            try:
                db.rollback()
            except Exception:
                pass
            if attempt < 2:
                continue
            if strict_env() or db_enabled():
                raise _store_unavailable() from None
            return None
        except Exception as exc:  # noqa: BLE001
            try:
                db.rollback()
            except Exception:
                pass
            if strict_env() or db_enabled():
                raise _store_unavailable() from exc
            return None
        finally:
            db.close()
    return None


def store_challenge(challenge_id: str, payload: dict, ttl_seconds: int) -> bool:
    """Persist one-time captcha digest/bindings.  Strict environments require DB."""
    db = _session(required=strict_env())
    if db is None:
        return False
    try:
        from app.models.auth_risk import AuthChallengeState

        now = datetime.utcnow()
        digest = _key_hash(challenge_id)
        old = db.scalars(select(AuthChallengeState).where(
            AuthChallengeState.challenge_id_hash == digest,
        ).with_for_update()).first()
        if old is not None:
            db.delete(old)
            db.flush()
        db.add(AuthChallengeState(
            challenge_id_hash=digest,
            payload_json=dict(payload or {}),
            expires_at=now + timedelta(seconds=max(1, int(ttl_seconds))),
        ))
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        if strict_env() or db_enabled():
            raise _store_unavailable("验证码持久化存储暂时不可用") from exc
        return False
    finally:
        db.close()


def consume_challenge(challenge_id: str) -> dict | None:
    """Atomically consume a captcha exactly once across workers/restarts."""
    db = _session(required=strict_env())
    if db is None:
        return None
    try:
        from app.models.auth_risk import AuthChallengeState

        now = datetime.utcnow()
        row = db.scalars(select(AuthChallengeState).where(
            AuthChallengeState.challenge_id_hash == _key_hash(challenge_id),
        ).with_for_update()).first()
        if row is None or row.consumed_at is not None or row.expires_at <= now:
            if row is not None and row.expires_at <= now and row.consumed_at is None:
                row.consumed_at = now
                db.commit()
            return None
        payload = dict(row.payload_json or {})
        row.consumed_at = now
        db.commit()
        return payload
    except Exception as exc:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        if strict_env() or db_enabled():
            raise _store_unavailable("验证码持久化存储暂时不可用") from exc
        return None
    finally:
        db.close()
