"""
P10 · 安全令牌存储（DB 持久化 + 内存回落）
────────────────────────────────────────────────────────────
- refreshToken 签发/轮换/吊销：DB_ENABLED=true 时落 t_auth_refresh_token
  （只存 sha256 哈希，多 worker 共享、重启存活）；否则内存（演示模式）。
- accessToken jti 黑名单：同上，落 t_auth_blocked_jti。
- 登录失败计数 / 滑动窗口限流：保持进程内存（单实例语义即可接受；
  Nginx 层可另加全局限流）。
"""
from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from app.core.config import settings

REFRESH_TTL = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
LOCK_THRESHOLD = 5
LOCK_SECONDS = 15 * 60

_refresh: dict[str, dict] = {}          # refreshToken -> {claims, exp}（内存回落）
_blocked_jti: dict[str, float] = {}     # jti -> exp（内存回落 + L1 缓存）
_allowed_jti: dict[str, float] = {}     # jti -> short L1 expiry; avoids DB-per-request when Redis is down
_fail: dict[str, list] = {}             # key -> [count, first_ts, locked_until]
_buckets: dict[str, deque] = defaultdict(deque)


def _now() -> float:
    return time.time()


def _tok_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode()).hexdigest()


def _db(*, required: bool = False):
    """DB 可用则返回 session。required=True 时不可用则抛错（安全写路径）。"""
    from app.core.config import settings
    from app.core.exceptions import AppException
    try:
        from app.db.session import db_enabled, get_sessionmaker
        if not db_enabled():
            if required and settings.is_prod:
                raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储不可用（生产必须启用数据库）",
                                   http_status=503)
            return None
        return get_sessionmaker()()
    except AppException:
        raise
    except Exception:  # noqa: BLE001
        if required or settings.is_prod:
            raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503)
        return None


# ── refreshToken ──
def issue_refresh(claims: dict) -> str:
    from app.core.config import settings
    from app.core.exceptions import AppException
    token = secrets.token_urlsafe(48)
    # 生产或 DB 开启：必须持久化，禁止仅内存签发
    from app.db.session import db_enabled
    must_persist = settings.is_prod or db_enabled()
    db = _db(required=must_persist)
    if db is not None:
        try:
            from app.models import AuthRefreshToken
            db.add(AuthRefreshToken(token_hash=_tok_hash(token),
                                    user_id=str(claims.get("userId") or ""),
                                    claims_json=dict(claims),
                                    expires_at=datetime.utcnow() + timedelta(seconds=REFRESH_TTL)))
            db.commit()
            return token
        except AppException:
            raise
        except Exception as e:  # noqa: BLE001
            try:
                db.rollback()
            except Exception:
                pass
            if must_persist:
                raise AppException("AUTH_STORE_UNAVAILABLE", "无法签发刷新令牌：认证存储写入失败",
                                   http_status=503) from e
        finally:
            db.close()
    if must_persist:
        raise AppException("AUTH_STORE_UNAVAILABLE", "无法签发刷新令牌：认证存储不可用", http_status=503)
    _refresh[token] = {"claims": dict(claims), "exp": _now() + REFRESH_TTL}
    return token


def consume_refresh(token: str) -> dict | None:
    """校验并轮换：旧 refresh 立即作废，返回 claims；无效/过期返回 None。
    DB 模式用「删除即消费」保证并发下同一 refresh 只能成功一次。
    生产/DB 开启时查询失败不得静默回落内存。"""
    from app.core.config import settings
    from app.core.exceptions import AppException
    from app.db.session import db_enabled
    must_persist = settings.is_prod or db_enabled()
    db = _db(required=must_persist)
    if db is not None:
        try:
            from sqlalchemy import delete, select
            from app.models import AuthRefreshToken
            h = _tok_hash(token or "")
            row = db.scalars(select(AuthRefreshToken).where(
                AuthRefreshToken.token_hash == h)).first()
            if row is None:
                # 仅演示模式允许兼容进程内存中的旧 token
                if not must_persist:
                    return _consume_refresh_memory(token)
                return None
            claims = dict(row.claims_json or {})
            expired = row.expires_at < datetime.utcnow()
            res = db.execute(delete(AuthRefreshToken).where(
                AuthRefreshToken.token_hash == h))
            db.commit()
            if expired or (res.rowcount or 0) == 0:
                return None  # 过期，或已被并发消费
            return claims
        except AppException:
            raise
        except Exception as e:  # noqa: BLE001
            try:
                db.rollback()
            except Exception:
                pass
            if must_persist:
                raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503) from e
            return _consume_refresh_memory(token)
        finally:
            db.close()
    return _consume_refresh_memory(token)


def _consume_refresh_memory(token: str) -> dict | None:
    item = _refresh.pop(token or "", None)
    if not item or item["exp"] < _now():
        return None
    return item["claims"]


def revoke_refresh_by_user(user_id: str) -> int:
    """吊销用户全部 refresh。DB 开启时写入失败抛错，禁止假成功。"""
    from app.core.config import settings
    from app.core.exceptions import AppException
    from app.db.session import db_enabled
    n = 0
    must_persist = settings.is_prod or db_enabled()
    db = _db(required=must_persist)
    if db is not None:
        try:
            from sqlalchemy import delete
            from app.models import AuthRefreshToken
            res = db.execute(delete(AuthRefreshToken).where(
                AuthRefreshToken.user_id == str(user_id)))
            db.commit()
            n += int(res.rowcount or 0)
        except AppException:
            raise
        except Exception as e:  # noqa: BLE001
            try:
                db.rollback()
            except Exception:
                pass
            if must_persist:
                raise AppException("AUTH_STORE_UNAVAILABLE", "无法吊销刷新令牌：认证存储写入失败",
                                   http_status=503) from e
        finally:
            db.close()
    elif must_persist:
        raise AppException("AUTH_STORE_UNAVAILABLE", "无法吊销刷新令牌：认证存储不可用", http_status=503)
    dead = [t for t, v in _refresh.items() if v["claims"].get("userId") == user_id]
    for t in dead:
        _refresh.pop(t, None)
    return n + len(dead)


# ── accessToken 黑名单（logout 即失效）──
def block_jti(jti: str, exp_ts: float | None = None) -> bool:
    """拉黑 access jti。返回是否完成持久化（生产必须 True）。"""
    from app.core.config import settings
    from app.core.exceptions import AppException
    from app.db.session import db_enabled
    if not jti:
        return False
    exp = exp_ts or (_now() + 7200)
    _blocked_jti[jti] = exp
    _allowed_jti.pop(jti, None)
    from app.core.redis_client import cache_set
    cache_set(f"auth:jti:{jti}", "1", max(1, int(exp - _now())))
    must_persist = settings.is_prod or db_enabled()
    db = _db(required=must_persist)
    persisted = not must_persist
    if db is not None:
        try:
            from app.models import AuthBlockedJti
            db.add(AuthBlockedJti(jti=jti, expires_at=datetime.utcfromtimestamp(exp)))
            db.commit()
            persisted = True
        except AppException:
            raise
        except Exception as e:  # noqa: BLE001
            try:
                db.rollback()
            except Exception:
                pass
            if must_persist:
                raise AppException("AUTH_STORE_UNAVAILABLE", "无法拉黑令牌：认证存储写入失败",
                                   http_status=503) from e
        finally:
            db.close()
    elif must_persist:
        raise AppException("AUTH_STORE_UNAVAILABLE", "无法拉黑令牌：认证存储不可用", http_status=503)
    for k in [k for k, v in _blocked_jti.items() if v < _now()]:
        _blocked_jti.pop(k, None)
    return persisted


def jti_blocked(jti: str | None) -> bool:
    if not jti:
        return False
    exp = _blocked_jti.get(jti)
    if exp is not None:
        if exp < _now():
            _blocked_jti.pop(jti, None)
            return False
        return True
    allowed_until = _allowed_jti.get(jti)
    if allowed_until is not None:
        if allowed_until >= _now():
            return False
        _allowed_jti.pop(jti, None)
    from app.core.redis_client import cache_get, cache_set, get_redis
    cached = cache_get(f"auth:jti:{jti}")
    if cached == "1":
        _blocked_jti[jti] = _now() + 60
        return True
    if cached == "0":
        _allowed_jti[jti] = _now() + 60
        return False
    db = _db()
    if db is not None:
        try:
            from sqlalchemy import select
            from app.models import AuthBlockedJti
            row = db.scalars(select(AuthBlockedJti).where(AuthBlockedJti.jti == jti)).first()
            if row is not None and row.expires_at >= datetime.utcnow():
                _blocked_jti[jti] = row.expires_at.timestamp()  # 回填 L1
                cache_set(f"auth:jti:{jti}", "1", max(1, int(row.expires_at.timestamp() - _now())))
                return True
        except Exception:  # noqa: BLE001 — 查询异常：生产/DB 模式 fail-closed
            from app.core.config import settings
            from app.core.exceptions import AppException
            from app.db.session import db_enabled
            if settings.is_prod or db_enabled():
                raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503)
        finally:
            db.close()
    # Cache a negative lookup.  Redis overwrites this immediately on logout;
    # when Redis is unavailable the short L1 TTL bounds the revocation delay.
    if get_redis() is not None:
        cache_set(f"auth:jti:{jti}", "0", 7200)
        _allowed_jti[jti] = _now() + 60
    else:
        _allowed_jti[jti] = _now() + 5
    return False


# ── 登录失败锁定 ──
def login_locked(key: str) -> int:
    """返回剩余锁定秒数（0=未锁定）。"""
    from app.core.redis_client import cache_get
    shared = cache_get(f"auth:login-lock:{key}")
    if shared:
        try:
            return max(0, int(float(shared) - _now()))
        except (TypeError, ValueError):
            pass
    rec = _fail.get(key)
    if not rec:
        return 0
    remain = int(rec[2] - _now())
    if remain <= 0 and rec[2]:
        _fail.pop(key, None)
        return 0
    return max(0, remain)


def record_login_failure(key: str, threshold: int | None = None,
                         lock_seconds: int | None = None) -> tuple[int, int]:
    """记一次失败。返回 (累计次数, 锁定剩余秒数)。达到阈值即锁定。
    threshold/lock_seconds 缺省用模块常量；调用方（auth 登录流）按租户 t_sys_config 传入，
    实现「系统配置·登录失败锁定阈值/时长」真实生效。"""
    from app.core.redis_client import cache_set, increment_with_ttl
    limit = int(threshold) if threshold else LOCK_THRESHOLD
    lock_for = int(lock_seconds) if lock_seconds else LOCK_SECONDS
    shared_count = increment_with_ttl(f"auth:login-fail:{key}", lock_for)
    if shared_count is not None:
        if shared_count >= limit:
            until = _now() + lock_for
            cache_set(f"auth:login-lock:{key}", str(until), lock_for)
            return shared_count, lock_for
        return shared_count, 0
    rec = _fail.setdefault(key, [0, _now(), 0.0])
    rec[0] += 1
    if rec[0] >= limit:
        rec[2] = _now() + lock_for
        return rec[0], lock_for
    return rec[0], 0


def reset_login_failures(key: str) -> None:
    from app.core.redis_client import cache_delete
    cache_delete(f"auth:login-fail:{key}", f"auth:login-lock:{key}")
    _fail.pop(key, None)


# ── 滑动窗口限流 ──
def rate_limit(bucket: str, limit: int, window: int = 60) -> bool:
    """True=放行；False=超限。"""
    from app.core.redis_client import fixed_window_allow
    shared = fixed_window_allow(bucket, limit, window)
    if shared is not None:
        return shared
    q = _buckets[bucket]
    now = _now()
    while q and q[0] <= now - window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def reset_all_for_tests() -> None:
    """仅测试用：清空全部内存态。"""
    _refresh.clear()
    _blocked_jti.clear()
    _allowed_jti.clear()
    _fail.clear()
    _buckets.clear()
