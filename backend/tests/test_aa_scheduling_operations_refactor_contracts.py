"""D5-S2 自动排课 / 排课增强 Move Only 结构合同。"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.modules.academic_affairs.routers import (
    academic_affairs as legacy,
    academic_affairs_bundle,
    academic_export_compat_router,
    schedule_core_router,
    scheduling_operations_router,
    scheduling_rule_router,
)


def _methods(route: APIRoute) -> set[str]:
    return set(route.methods or set()) - {"HEAD", "OPTIONS"}


def _first_route(path: str, method: str) -> APIRoute:
    for route in academic_affairs_bundle.build_router().routes:
        if isinstance(route, APIRoute) and route.path == path and method in _methods(route):
            return route
    raise AssertionError(f"missing route {method} {path}")


def _first_in(router, path: str, method: str) -> APIRoute:
    for route in router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in _methods(route):
            return route
    raise AssertionError(f"missing child route {method} {path}")


def _collect_permission_codes(value) -> set[str]:
    if isinstance(value, str):
        return {value} if value.startswith("academicAffairs.") else set()
    if isinstance(value, (list, tuple, set, frozenset)):
        out: set[str] = set()
        for item in value:
            out.update(_collect_permission_codes(item))
        return out
    return set()


def _permission_codes(route: APIRoute) -> set[str]:
    codes: set[str] = set()
    stack = list(route.dependant.dependencies)
    seen: set[int] = set()
    while stack:
        dep = stack.pop()
        if id(dep) in seen:
            continue
        seen.add(id(dep))
        call = getattr(dep, "call", None)
        for cell in getattr(call, "__closure__", None) or ():
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            codes.update(_collect_permission_codes(value))
        stack.extend(getattr(dep, "dependencies", None) or [])
    return codes


def _shapes(router) -> set[tuple[str, str]]:
    return {
        (route.path, method)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in _methods(route)
    }


def test_d5_s2_public_shapes_are_owned_by_scheduling_operations_router():
    expected = "app.modules.academic_affairs.routers.scheduling_operations_router"
    children = [route for route in scheduling_operations_router.router.routes if isinstance(route, APIRoute)]
    assert len(children) == 17
    for child in children:
        for method in _methods(child):
            public = _first_route(child.path, method)
            assert public.endpoint.__module__ == expected, (method, child.path, public.endpoint.__module__)


def test_d5_s2_move_only_preserves_legacy_permissions_and_route_metadata():
    for child in scheduling_operations_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        for method in _methods(child):
            old = _first_in(legacy.router, child.path, method)
            assert _permission_codes(child) == _permission_codes(old), (method, child.path)
            assert child.summary == old.summary, (method, child.path)
            assert child.status_code == old.status_code, (method, child.path)
            assert child.response_model == old.response_model, (method, child.path)


def test_d5_s2_reuses_legacy_contract_objects_services_and_constants():
    for name in ("AvailabilityBody", "AvailReviewBody", "TeacherObjectBody", "AdjustItemBody"):
        assert getattr(scheduling_operations_router, name) is getattr(legacy, name), name

    assert scheduling_operations_router.sched_svc is legacy.sched_svc
    assert scheduling_operations_router.scheduling_svc is legacy.scheduling_svc
    assert scheduling_operations_router.autosched_svc is legacy.autosched_svc
    assert scheduling_operations_router.xlsx_util is legacy.xlsx_util
    assert scheduling_operations_router.AppException is legacy.AppException

    for name in (
        "_XLSX_MEDIA",
        "_SCHED_RULE",
        "_SCHED_AVAIL",
        "_SCHED_VIEW",
        "_SCHED_EDIT",
        "_SCHED_IMPORT",
        "_SCHED_ARCHIVE",
        "_SCHED_TEACHER_CONFIRM",
    ):
        assert getattr(scheduling_operations_router, name) == getattr(legacy, name), name


def test_d5_s2_does_not_take_schedule_core_rules_or_export_owners():
    s2_shapes = _shapes(scheduling_operations_router.router)
    assert s2_shapes.isdisjoint(_shapes(schedule_core_router.router))

    for route in scheduling_rule_router.router.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in _methods(route):
            assert (route.path, method) not in s2_shapes
            public = _first_route(route.path, method)
            assert public.endpoint.__module__ == "app.modules.academic_affairs.routers.scheduling_rule_router"

    assert ("/academic-affairs/schedule/export", "POST") not in s2_shapes
    export = _first_route("/academic-affairs/schedule/export", "POST")
    assert export.endpoint.__module__ == "app.modules.academic_affairs.routers.academic_export_compat_router"
    assert any(
        isinstance(route, APIRoute)
        and route.path == "/academic-affairs/schedule/export"
        and "POST" in _methods(route)
        for route in academic_export_compat_router.router.routes
    )


def test_d5_s2_schedule_core_remains_public_owner():
    expected = "app.modules.academic_affairs.routers.schedule_core_router"
    for child in schedule_core_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        for method in _methods(child):
            public = _first_route(child.path, method)
            assert public.endpoint.__module__ == expected, (method, child.path, public.endpoint.__module__)


def test_d5_s2_routes_are_visible_in_final_openapi():
    from app.core.config import settings
    from app.main import app

    schema = app.openapi()
    for child in scheduling_operations_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        public_path = f"{settings.API_V1_PREFIX}{child.path}"
        assert public_path in schema["paths"], public_path
        for method in _methods(child):
            assert method.lower() in schema["paths"][public_path], (method, public_path)
