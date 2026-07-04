"""
P5.5A · 内存态安全存储（基础版，重启即失；生产迁 Redis 时仅换本模块实现）
────────────────────────────────────────────────────────────
- refreshToken 签发/轮换/吊销
- accessToken jti 黑名单（logout 即失效）
- 登录失败计数：5 次锁定 15 分钟
- 滑动窗口限流：登录 10 次/IP/分钟、上传 20 次/用户/分钟、导出 5 次/用户/分钟
"""
from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque

REFRESH_TTL = 7 * 24 * 3600
LOCK_THRESHOLD = 5
LOCK_SECONDS = 15 * 60

_refresh: dict[str, dict] = {}          # refreshToken -> {claims, exp}
_blocked_jti: dict[str, float] = {}     # jti -> exp
_fail: dict[str, list] = {}             # key -> [count, first_ts, locked_until]
_buckets: dict[str, deque] = defaultdict(deque)


def _now() -> float:
    return time.time()


# ── refreshToken ──
def issue_refresh(claims: dict) -> str:
    token = secrets.token_urlsafe(48)
    _refresh[token] = {"claims": dict(claims), "exp": _now() + REFRESH_TTL}
    return token


def consume_refresh(token: str) -> dict | None:
    """校验并轮换：旧 refresh 立即作废，返回 claims；无效/过期返回 None。"""
    item = _refresh.pop(token or "", None)
    if not item or item["exp"] < _now():
        return None
    return item["claims"]


def revoke_refresh_by_user(user_id: str) -> int:
    dead = [t for t, v in _refresh.items() if v["claims"].get("userId") == user_id]
    for t in dead:
        _refresh.pop(t, None)
    return len(dead)


# ── accessToken 黑名单（logout 即失效）──
def block_jti(jti: str, exp_ts: float | None = None) -> None:
    if jti:
        _blocked_jti[jti] = exp_ts or (_now() + 7200)
    # 顺手清理过期项
    for k in [k for k, v in _blocked_jti.items() if v < _now()]:
        _blocked_jti.pop(k, None)


def jti_blocked(jti: str | None) -> bool:
    if not jti:
        return False
    exp = _blocked_jti.get(jti)
    if exp is None:
        return False
    if exp < _now():
        _blocked_jti.pop(jti, None)
        return False
    return True


# ── 登录失败锁定 ──
def login_locked(key: str) -> int:
    """返回剩余锁定秒数（0=未锁定）。"""
    rec = _fail.get(key)
    if not rec:
        return 0
    remain = int(rec[2] - _now())
    if remain <= 0 and rec[2]:
        _fail.pop(key, None)
        return 0
    return max(0, remain)


def record_login_failure(key: str) -> tuple[int, int]:
    """记一次失败。返回 (累计次数, 锁定剩余秒数)。达到阈值即锁定 15 分钟。"""
    rec = _fail.setdefault(key, [0, _now(), 0.0])
    rec[0] += 1
    if rec[0] >= LOCK_THRESHOLD:
        rec[2] = _now() + LOCK_SECONDS
        return rec[0], LOCK_SECONDS
    return rec[0], 0


def reset_login_failures(key: str) -> None:
    _fail.pop(key, None)


# ── 滑动窗口限流 ──
def rate_limit(bucket: str, limit: int, window: int = 60) -> bool:
    """True=放行；False=超限。"""
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
    _fail.clear()
    _buckets.clear()
