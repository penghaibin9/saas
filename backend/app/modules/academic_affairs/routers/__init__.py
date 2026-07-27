"""教务中心 API 路由聚合。"""
from __future__ import annotations

from . import academic_affairs as academic_affairs
from .dashboard_readiness_router import router as dashboard_readiness_router
from .dynamic_grade_router import router as dynamic_grade_router
from .grade_identity_router import router as grade_identity_router
from .mobile_grade_entry_router import router as mobile_grade_entry_router
from .scheduling_rule_router import router as scheduling_rule_router
from .stats_snapshot_router import router as stats_snapshot_router
from .teaching_class_router import router as teaching_class_router
from .term_detail_router import router as term_detail_router


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


def _append_routes(router) -> None:
    for route in router.routes:
        signature = (
            getattr(route, "path", ""),
            tuple(sorted(getattr(route, "methods", set()) or set())),
        )
        if signature not in _existing:
            academic_affairs.router.routes.append(route)
            _existing.add(signature)


# route_registration 继续只注册 academic_affairs.router。
# 移除旧请求体后再聚合V2/R10小路由，避免同路径首条路由抢占。
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
_append_routes(dashboard_readiness_router)
_append_routes(term_detail_router)
_append_routes(grade_identity_router)
_append_routes(dynamic_grade_router)
_append_routes(stats_snapshot_router)

# R5 的路由前缀是 /mobile/teacher/academic。直接追加 APIRoute，保持既有移动 URL，
# 同时复用 route_registration 给 academic_affairs.router 挂载的模块门禁。
_append_routes(mobile_grade_entry_router)
