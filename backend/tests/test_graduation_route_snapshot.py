"""毕业设计接口“实际生效路由”快照护栏。

FastAPI 按注册顺序命中第一个匹配路由。历史上同一路径在多个 router 重复声明，
后注册者永远不会执行。收口重复声明时，本测试保证：
1. 每个毕设接口（含 /mobile、/portal）实际执行的处理函数与快照一致（行为不变）；
2. 不再出现同一 (method, path) 被重复声明。

更新快照：设置环境变量 UPDATE_GRADUATION_ROUTE_SNAPSHOT=1 运行本测试。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.routing import APIRoute

SNAPSHOT = Path(__file__).parent / "fixtures" / "graduation_route_snapshot.json"


def _walk(routes, prefix, seen):
    for route in routes:
        if isinstance(route, APIRoute):
            path = prefix + route.path
            if "graduation" in path:
                for method in sorted(route.methods or []):
                    seen.setdefault(f"{method} {path}", []).append(
                        f"{route.endpoint.__module__}.{route.endpoint.__name__}")
            continue
        ctx = getattr(route, "include_context", None)
        original = getattr(route, "original_router", None)
        if ctx is not None and original is not None:
            _walk(original.routes, prefix + (ctx.prefix or ""), seen)
            continue
        sub = getattr(route, "routes", None)
        if sub:
            _walk(sub, prefix + (getattr(route, "path", "") or ""), seen)


def graduation_route_table() -> dict[str, list[str]]:
    from app.main import app

    seen: dict[str, list[str]] = {}
    _walk(app.routes, "", seen)
    return seen


def test_effective_graduation_routes_match_snapshot_and_have_no_shadowed_duplicates():
    table = graduation_route_table()
    effective = {key: handlers[0] for key, handlers in sorted(table.items())}
    if os.environ.get("UPDATE_GRADUATION_ROUTE_SNAPSHOT") == "1":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(effective, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    missing = sorted(set(expected) - set(effective))
    added = sorted(set(effective) - set(expected))
    changed = sorted(k for k in set(expected) & set(effective) if expected[k] != effective[k])
    assert not missing, f"接口丢失: {missing[:20]}"
    assert not changed, f"实际执行的处理函数发生变化: {[(k, expected[k], effective[k]) for k in changed[:20]]}"
    assert not added, f"新增接口需同步更新快照: {added[:20]}"
    duplicated = {k: v for k, v in table.items() if len(v) > 1}
    if os.environ.get("ALLOW_GRADUATION_ROUTE_DUPLICATES") != "1":
        assert not duplicated, f"仍有 {len(duplicated)} 个被遮蔽的重复声明: {list(duplicated)[:10]}"
