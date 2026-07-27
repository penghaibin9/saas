"""教务中心 API 路由聚合。"""
from __future__ import annotations

from . import academic_affairs as academic_affairs
from .grade_identity_router import router as grade_identity_router
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


def _legacy_grade_identity_route(route) -> bool:
    path = getattr(route, "path", "")
    methods = set(getattr(route, "methods", set()) or set())
    return "POST" in methods and path in {
        "/academic-affairs/grade-tasks",
        "/academic-affairs/makeup/batches/{bid}/enroll",
        "/academic-affairs/retake/apply",
        "/academic-affairs/exemption/apply",
    }


# route_registration 继续只注册 academic_affairs.router。
# 移除旧请求体后再聚合V2小路由，避免同路径首条路由抢占。
academic_affairs.router.routes[:] = [
    route for route in academic_affairs.router.routes
    if not _legacy_scheduling_rule_route(route) and not _legacy_grade_identity_route(route)
]
_existing = {
    (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", set()) or set())))
    for route in academic_affairs.router.routes
}
if not any(path == "/academic-affairs/scheduling/rules" for path, _methods in _existing):
    academic_affairs.router.include_router(scheduling_rule_router)
if not any(path == "/academic-affairs/teaching-classes" for path, _methods in _existing):
    academic_affairs.router.include_router(teaching_class_router)
for route in grade_identity_router.routes:
    signature = (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", set()) or set())))
    if signature not in _existing:
        academic_affairs.router.routes.append(route)
        _existing.add(signature)
