"""幂等控制：指纹校验 + PROCESSING 预占 + 成功/失败释放。

关键写操作优先配合业务库状态机；Redis 不可用时关键路径可用 DB 表 t_idempotency_record。
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from typing import Any, Iterator

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.redis_client import cache_delete, cache_get_json, cache_set_json, cache_set_json_if_absent

TTL_SECONDS = 15 * 60


def _fingerprint(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_key(user: dict, operation: str, raw_key: str) -> str:
    tenant_id = str(current_tenant_id() or user.get("tenantId") or "-")
    user_id = str(user.get("userId") or "-")
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"idempotency:{tenant_id}:{user_id}:{operation}:{key_hash}"


def begin(user: dict, operation: str, key: str | None, payload: Any) -> tuple[Any | None, tuple[str, str] | None]:
    """Return a cached result or an opaque handle to save a new result."""
    raw_key = (key or "").strip()
    if not raw_key:
        return None, None
    if len(raw_key) < 8 or len(raw_key) > 128:
        raise AppException("VALIDATION_ERROR", "Idempotency-Key 长度必须为 8 到 128 个字符")
    cache_key = _cache_key(user, operation, raw_key)
    fingerprint = _fingerprint(payload)
    cached = cache_get_json(cache_key)
    if isinstance(cached, dict):
        if cached.get("fingerprint") != fingerprint:
            raise AppException("DATA_CONFLICT", "同一个 Idempotency-Key 不能用于不同请求内容")
        if cached.get("state") == "PROCESSING":
            raise AppException("DATA_CONFLICT", "相同请求正在处理中，请勿重复提交")
        if cached.get("state") in ("DONE", "SUCCESS"):
            return cached.get("result"), None
        if cached.get("state") == "FINAL_FAILED":
            raise AppException("DATA_CONFLICT", "相同请求已最终失败，请更换 Idempotency-Key 后重试")

    reservation = {"fingerprint": fingerprint, "state": "PROCESSING"}
    acquired = cache_set_json_if_absent(cache_key, reservation, TTL_SECONDS)
    if acquired is False:
        cached = cache_get_json(cache_key)
        if isinstance(cached, dict) and cached.get("fingerprint") != fingerprint:
            raise AppException("DATA_CONFLICT", "同一个 Idempotency-Key 不能用于不同请求内容")
        if isinstance(cached, dict) and cached.get("state") in ("DONE", "SUCCESS"):
            return cached.get("result"), None
        raise AppException("DATA_CONFLICT", "相同请求正在处理中，请勿重复提交")
    if acquired is None:
        return None, None
    return None, (cache_key, fingerprint)


def finish(handle: tuple[str, str] | None, result: Any, ttl: int = TTL_SECONDS) -> None:
    if handle is None:
        return
    cache_key, fingerprint = handle
    if str(cache_key).startswith("db:"):
        _finish_db(int(str(cache_key)[3:]), fingerprint, result, state="SUCCESS")
        return
    cache_set_json(cache_key, {"fingerprint": fingerprint, "state": "SUCCESS", "result": result}, ttl)


def abort(handle: tuple[str, str] | None) -> None:
    """业务异常可重试：释放预占，允许同 key 重试。"""
    if handle is None:
        return
    cache_key, fingerprint = handle
    if str(cache_key).startswith("db:"):
        _finish_db(int(str(cache_key)[3:]), fingerprint, None, state="RETRYABLE_FAILED", delete=True)
        return
    cache_delete(cache_key)


def fail(handle: tuple[str, str] | None, *, final: bool = False, error: str | None = None,
         ttl: int = TTL_SECONDS) -> None:
    """标记失败。final=True 时同 key 不可再跑；否则释放。"""
    if handle is None:
        return
    cache_key, fingerprint = handle
    if str(cache_key).startswith("db:"):
        _finish_db(int(str(cache_key)[3:]), fingerprint, {"error": error},
                   state="FINAL_FAILED" if final else "RETRYABLE_FAILED",
                   delete=not final)
        return
    if final:
        cache_set_json(cache_key, {
            "fingerprint": fingerprint, "state": "FINAL_FAILED", "error": error or "",
        }, ttl)
    else:
        cache_delete(cache_key)


class _Guard:
    def __init__(self, handle: tuple[str, str] | None, cached: Any):
        self.handle = handle
        self.cached = cached
        self._finished = False

    def success(self, result: Any) -> Any:
        finish(self.handle, result)
        self._finished = True
        return result


@contextmanager
def idempotency_guard(user: dict, operation: str, key: str | None, payload: Any,
                      *, require_store: bool = False) -> Iterator[_Guard]:
    """with idempotency_guard(...) as g:
         if g.cached is not None: return g.cached
         result = execute()
         g.success(result)
    """
    cached, handle = begin(user, operation, key, payload)
    if require_store and (key or "").strip() and handle is None and cached is None:
        from app.db.session import db_enabled
        if db_enabled():
            cached, handle = _begin_db(user, operation, key, payload)
        if handle is None and cached is None and (key or "").strip():
            raise AppException("IDEMPOTENCY_STORE_UNAVAILABLE", "幂等存储不可用，请稍后重试",
                               http_status=503)
    guard = _Guard(handle, cached)
    try:
        yield guard
        if handle and not guard._finished and cached is None:
            abort(handle)
    except AppException:
        abort(handle)
        raise
    except Exception:
        abort(handle)
        raise


def _begin_db(user: dict, operation: str, key: str | None, payload: Any):
    from datetime import datetime, timedelta

    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.models.idempotency import IdempotencyRecord
    from app.services.db_service import _tid, session

    raw_key = (key or "").strip()
    if not raw_key:
        return None, None
    tenant_id = _tid()
    user_id = str(user.get("userId") or "-")
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    fingerprint = _fingerprint(payload)
    with session() as db:
        row = db.scalars(select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key_hash == key_hash,
        )).first()
        if row:
            if row.fingerprint != fingerprint:
                raise AppException("DATA_CONFLICT", "同一个 Idempotency-Key 不能用于不同请求内容")
            if row.state == "PROCESSING" and row.expires_at and row.expires_at > datetime.utcnow():
                raise AppException("DATA_CONFLICT", "相同请求正在处理中，请勿重复提交")
            if row.state in ("SUCCESS", "DONE"):
                return row.result_json, None
            if row.state == "FINAL_FAILED":
                raise AppException("DATA_CONFLICT", "相同请求已最终失败，请更换 Idempotency-Key 后重试")
            row.state = "PROCESSING"
            row.fingerprint = fingerprint
            row.expires_at = datetime.utcnow() + timedelta(seconds=TTL_SECONDS)
            row.result_json = None
            db.commit()
            return None, ("db:" + str(row.id), fingerprint)
        row = IdempotencyRecord(
            tenant_id=tenant_id, user_id=user_id, operation=operation,
            key_hash=key_hash, fingerprint=fingerprint, state="PROCESSING",
            expires_at=datetime.utcnow() + timedelta(seconds=TTL_SECONDS),
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except IntegrityError:
            db.rollback()
            return _begin_db(user, operation, key, payload)
        return None, ("db:" + str(row.id), fingerprint)


def _finish_db(row_id: int, fingerprint: str, result: Any, *, state: str, delete: bool = False) -> None:
    from app.models.idempotency import IdempotencyRecord
    from app.services.db_service import session

    with session() as db:
        row = db.get(IdempotencyRecord, row_id)
        if not row:
            return
        if delete or state == "RETRYABLE_FAILED":
            db.delete(row)
        else:
            row.state = state
            row.fingerprint = fingerprint
            row.result_json = result
        db.commit()
