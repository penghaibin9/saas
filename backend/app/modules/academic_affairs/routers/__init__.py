"""教务中心 API 路由聚合。"""
from __future__ import annotations

from . import academic_affairs as academic_affairs
from .scheduling_rule_router import router as scheduling_rule_router
from .teaching_class_router import router as teaching_class_router


def _legacy_scheduling_rule_route(route) -> bool:
    path = getattr(route, "path", "")
    methods = set(getattr(route, "methods", set()) or set())
    if path == "/academic-affairs/scheduling/rules" and methods.intersection({"GET", "PUT"}):
        return True
    if path == "/academic-affairs/scheduling/rules/{ruleId}" and "DELETE" in methods:
        return True
    return False


# route_registration 继续只注册 academic_affairs.router。
# 先移除旧总路由中 ruleValue=dict 的三个规则端点，再聚合 V2-03 正确类型契约，避免同路径首条路由抢占。
academic_affairs.router.routes[:] = [
    route for route in academic_affairs.router.routes
    if not _legacy_scheduling_rule_route(route)
]
_existing_paths = {getattr(route, "path", "") for route in academic_affairs.router.routes}
if "/academic-affairs/scheduling/rules" not in _existing_paths:
    academic_affairs.router.include_router(scheduling_rule_router)
if "/academic-affairs/teaching-classes" not in _existing_paths:
    academic_affairs.router.include_router(teaching_class_router)
