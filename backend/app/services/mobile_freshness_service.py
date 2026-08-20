"""V3 §5.4 projectionVersion / freshness 合同。

V3 深审 P1-12：只写「写后 invalidate」不够。Home / 工作台是多域聚合投影，任何一个域
（待办、消息、课表、成绩、实习、毕设）落库后，客户端手里那份 20s 内的旧投影都应当立刻
失效——否则学生提交完请假回到首页，看到的仍是提交前的状态，直到 TTL 过期。

做法很小：每个 (租户, 主体, 投影域) 维护一个单调递增计数器。

- 域事实变化时 :func:`bump` 自增对应计数器；
- 投影 DTO 带上 ``asOf`` 与 ``projectionVersion``；
- 客户端只要发现 ``projectionVersion`` 变了，就必须丢弃旧请求与旧页面结果，
  不能再拿 20s 本地 freshness 顶着。

Redis 不可用时（本地开发/演示模式）没有服务端缓存，每次请求本来就是新鲜的，
此时退化成构建时刻本身，语义仍然自洽：版本变了 = 数据可能变了。
"""
from __future__ import annotations

import time

#: 参与 Home/工作台投影的域。新增域时必须同时在写路径上 bump，否则首页会陈旧。
PROJECTIONS = (
    "todo",
    "message",
    "schedule",
    "grade",
    "internship",
    "graduation",
    "case",
)

_VERSION_TTL = 7 * 24 * 3600


def _key(tenant_id, subject_id, projection: str) -> str:
    return f"freshness:{tenant_id or '-'}:{subject_id or '-'}:{projection}"


def _subject(user: dict) -> tuple:
    user = user or {}
    return user.get("tenantId"), user.get("studentId") or user.get("userId")


def bump(user: dict, projection: str) -> int | None:
    """域事实变化后自增投影版本。未知域名直接报错，避免打错字导致永不失效。"""
    if projection not in PROJECTIONS:
        raise ValueError(f"未登记的投影域：{projection}")
    from app.core.redis_client import increment_with_ttl

    tenant_id, subject_id = _subject(user)
    return increment_with_ttl(_key(tenant_id, subject_id, projection), _VERSION_TTL)


def current_versions(user: dict, projections: tuple[str, ...] = PROJECTIONS) -> dict[str, int]:
    """读取当前各域版本；缺失视为 0（尚未发生过变化）。"""
    from app.core.redis_client import cache_get

    tenant_id, subject_id = _subject(user)
    versions: dict[str, int] = {}
    for projection in projections:
        raw = cache_get(_key(tenant_id, subject_id, projection))
        try:
            versions[projection] = int(raw) if raw is not None else 0
        except (TypeError, ValueError):
            versions[projection] = 0
    return versions


def projection_version(user: dict, projections: tuple[str, ...] = PROJECTIONS) -> str:
    """把参与该投影的所有域版本压成一个可比较的字符串。

    客户端只需比较是否相等，不需要理解内部结构。
    """
    versions = current_versions(user, projections)
    if not any(versions.values()):
        # 没有任何域被 bump 过（通常是 Redis 不可用）：退化成秒级构建时刻。
        return f"t{int(time.time())}"
    return "-".join(f"{name}{versions[name]}" for name in projections if name in versions)
