"""D5-S4 调停课 Move Only 结构合同。"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.modules.academic_affairs.routers import (
    academic_affairs as legacy,
    academic_affairs_bundle,
    schedule_change_router,
    schedule_core_router,
    scheduling_operations_router,
    scheduling_rule_router,
    teaching_resource_router,
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


def test_d5_s4_public_shapes_are_owned_by_schedule_change_router():
    expected = "app.modules.academic_affairs.routers.schedule_change_router"
    children = [route for route in schedule_change_router.router.routes if isinstance(route, APIRoute)]
    assert len(children) == 9
    for child in children:
        for method in _methods(child):
            public = _first_route(child.path, method)
            assert public.endpoint.__module__ == expected, (method, child.path, public.endpoint.__module__)


def test_d5_s4_move_only_preserves_legacy_permissions_and_route_metadata():
    for child in schedule_change_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        for method in _methods(child):
            old = _first_in(legacy.router, child.path, method)
            assert _permission_codes(child) == _permission_codes(old), (method, child.path)
            assert child.summary == old.summary, (method, child.path)
            assert child.status_code == old.status_code, (method, child.path)
            assert child.response_model == old.response_model, (method, child.path)


def test_d5_s4_reuses_legacy_contract_objects_service_and_review_dependency():
    for name in (
        "ScheduleChangeSubmit",
        "ScheduleChangeReviewBody",
        "ScheduleChangeCancelBody",
        "ScheduleChangeConflictCheckBody",
    ):
        assert getattr(schedule_change_router, name) is getattr(legacy, name), name
    assert schedule_change_router.sched_change_svc is legacy.sched_change_svc
    assert schedule_change_router._SC_REVIEW is legacy._SC_REVIEW


def test_d5_s4_static_get_paths_precede_dynamic_detail():
    routes = [route for route in schedule_change_router.router.routes if isinstance(route, APIRoute)]
    get_shapes = [route.path for route in routes if "GET" in _methods(route)]
    dynamic = "/academic-affairs/schedule-change/{changeId}"
    assert get_shapes.index("/academic-affairs/schedule-change/stats") < get_shapes.index(dynamic)
    assert get_shapes.index("/academic-affairs/schedule-change/archive") < get_shapes.index(dynamic)


def test_d5_s4_does_not_take_other_d5_or_scheduling_rule_owners():
    change_shapes = _shapes(schedule_change_router.router)
    for router in (
        schedule_core_router.router,
        scheduling_operations_router.router,
        teaching_resource_router.router,
        scheduling_rule_router.router,
    ):
        assert change_shapes.isdisjoint(_shapes(router))


def test_d5_s4_previous_d5_owners_remain_public():
    for router, expected in (
        (schedule_core_router.router, "app.modules.academic_affairs.routers.schedule_core_router"),
        (scheduling_operations_router.router, "app.modules.academic_affairs.routers.scheduling_operations_router"),
        (teaching_resource_router.router, "app.modules.academic_affairs.routers.teaching_resource_router"),
        (scheduling_rule_router.router, "app.modules.academic_affairs.routers.scheduling_rule_router"),
    ):
        for child in router.routes:
            if not isinstance(child, APIRoute):
                continue
            for method in _methods(child):
                public = _first_route(child.path, method)
                assert public.endpoint.__module__ == expected, (method, child.path, public.endpoint.__module__)


def test_d5_s4_routes_are_visible_in_final_openapi():
    from app.core.config import settings
    from app.main import app

    schema = app.openapi()
    for child in schedule_change_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        public_path = f"{settings.API_V1_PREFIX}{child.path}"
        assert public_path in schema["paths"], public_path
        for method in _methods(child):
            assert method.lower() in schema["paths"][public_path], (method, public_path)
