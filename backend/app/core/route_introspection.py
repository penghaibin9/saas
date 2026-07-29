"""兼容 FastAPI 扁平路由与嵌套路由的有效 API 路由遍历。"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from fastapi.routing import APIRoute

try:
    # FastAPI 0.139+：include_router 保存为嵌套节点，必须通过有效上下文展开。
    from fastapi.routing import iter_route_contexts as _iter_route_contexts
except ImportError:  # FastAPI 旧版本仍是扁平 APIRoute 列表。
    _iter_route_contexts = None


def iter_effective_api_routes(routes: Iterable[Any]) -> Iterator[Any]:
    """产出带最终 prefix、依赖和 methods 的有效 APIRoute/RouteContext。"""
    if _iter_route_contexts is None:
        for route in routes:
            if isinstance(route, APIRoute):
                yield route
        return

    for route_context in _iter_route_contexts(list(routes)):
        if isinstance(route_context.original_route, APIRoute):
            yield route_context
