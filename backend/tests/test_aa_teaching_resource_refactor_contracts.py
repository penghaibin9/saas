"""D5-S3 教学资源 Move Only 结构合同。"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.modules.academic_affairs.routers import (
    academic_affairs as legacy,
    academic_affairs_bundle,
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


def test_d5_s3_public_shapes_are_owned_by_teaching_resource_router():
    expected = "app.modules.academic_affairs.routers.teaching_resource_router"
    children = [route for route in teaching_resource_router.router.routes if isinstance(route, APIRoute)]
    assert len(children) == 34
    for child in children:
        for method in _methods(child):
            public = _first_route(child.path, method)
            assert public.endpoint.__module__ == expected, (method, child.path, public.endpoint.__module__)


def test_d5_s3_move_only_preserves_legacy_permissions_and_route_metadata():
    for child in teaching_resource_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        for method in _methods(child):
            old = _first_in(legacy.router, child.path, method)
            assert _permission_codes(child) == _permission_codes(old), (method, child.path)
            assert child.summary == old.summary, (method, child.path)
            assert child.status_code == old.status_code, (method, child.path)
            assert child.response_model == old.response_model, (method, child.path)


def test_d5_s3_reuses_legacy_contract_objects_and_resource_service():
    for name in (
        "ClassroomCreate",
        "ClassroomUpdate",
        "ClassroomStatusBody",
        "ClassroomBookBody",
        "BookingReviewBody",
        "LabCreate",
        "LabUpdate",
        "LabStatusBody",
        "LabBookBody",
        "EquipmentCreate",
        "EquipmentUpdate",
        "EquipmentStatusBody",
        "RepairReportBody",
        "RepairCompleteBody",
        "RepairCancelBody",
    ):
        assert getattr(teaching_resource_router, name) is getattr(legacy, name), name
    assert teaching_resource_router.resource_svc is legacy.resource_svc


def test_d5_s3_keeps_static_booking_paths_before_dynamic_detail_paths():
    routes = [route for route in teaching_resource_router.router.routes if isinstance(route, APIRoute)]
    get_shapes = [route.path for route in routes if "GET" in _methods(route)]

    assert get_shapes.index("/academic-affairs/classrooms/options") < get_shapes.index(
        "/academic-affairs/classrooms/{classroomId}"
    )
    assert get_shapes.index("/academic-affairs/classrooms/bookings") < get_shapes.index(
        "/academic-affairs/classrooms/{classroomId}"
    )
    assert get_shapes.index("/academic-affairs/labs/options") < get_shapes.index(
        "/academic-affairs/labs/{labId}"
    )
    assert get_shapes.index("/academic-affairs/labs/bookings") < get_shapes.index(
        "/academic-affairs/labs/{labId}"
    )


def test_d5_s3_does_not_take_schedule_or_scheduling_rule_owners():
    resource_shapes = _shapes(teaching_resource_router.router)
    assert resource_shapes.isdisjoint(_shapes(schedule_core_router.router))
    assert resource_shapes.isdisjoint(_shapes(scheduling_operations_router.router))
    assert resource_shapes.isdisjoint(_shapes(scheduling_rule_router.router))

    for router, expected in (
        (schedule_core_router.router, "app.modules.academic_affairs.routers.schedule_core_router"),
        (scheduling_operations_router.router, "app.modules.academic_affairs.routers.scheduling_operations_router"),
        (scheduling_rule_router.router, "app.modules.academic_affairs.routers.scheduling_rule_router"),
    ):
        for child in router.routes:
            if not isinstance(child, APIRoute):
                continue
            for method in _methods(child):
                public = _first_route(child.path, method)
                assert public.endpoint.__module__ == expected, (method, child.path, public.endpoint.__module__)


def test_d5_s3_routes_are_visible_in_final_openapi():
    from app.core.config import settings
    from app.main import app

    schema = app.openapi()
    for child in teaching_resource_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        public_path = f"{settings.API_V1_PREFIX}{child.path}"
        assert public_path in schema["paths"], public_path
        for method in _methods(child):
            assert method.lower() in schema["paths"][public_path], (method, public_path)
