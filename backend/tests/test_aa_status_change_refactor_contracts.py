"""D3-S 学籍异动 Move Only 结构合同。"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.modules.academic_affairs.routers import (
    academic_affairs_bundle,
    status_change_router,
    status_change_temporal_router,
)


def _methods(route: APIRoute) -> set[str]:
    return set(route.methods or set()) - {"HEAD", "OPTIONS"}


def _first_route(path: str, method: str) -> APIRoute:
    for route in academic_affairs_bundle.build_router().routes:
        if isinstance(route, APIRoute) and route.path == path and method in _methods(route):
            return route
    raise AssertionError(f"missing route {method} {path}")


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


def test_d3_public_shapes_are_owned_by_status_change_router():
    expected = "app.modules.academic_affairs.routers.status_change_router"
    children = [r for r in status_change_router.router.routes if isinstance(r, APIRoute)]
    assert children
    for child in children:
        for method in _methods(child):
            public = _first_route(child.path, method)
            assert public.endpoint.__module__ == expected, (method, child.path, public.endpoint.__module__)


def test_d3_scheduled_shape_keeps_temporal_owner():
    route = _first_route("/academic-affairs/status-changes/scheduled", "POST")
    assert route.endpoint.__module__ == "app.modules.academic_affairs.routers.status_change_temporal_router"


def test_d3_main_router_does_not_duplicate_temporal_scheduled_shape():
    shapes = {
        (route.path, method)
        for route in status_change_router.router.routes
        if isinstance(route, APIRoute)
        for method in _methods(route)
    }
    assert ("/academic-affairs/status-changes/scheduled", "POST") not in shapes
    temporal_shapes = {
        (route.path, method)
        for route in status_change_temporal_router.router.routes
        if isinstance(route, APIRoute)
        for method in _methods(route)
    }
    assert ("/academic-affairs/status-changes/scheduled", "POST") in temporal_shapes


def test_d3_stats_literal_stays_before_change_id_parameter():
    paths = [r.path for r in status_change_router.router.routes if isinstance(r, APIRoute)]
    assert paths.index("/academic-affairs/status-changes/stats") < paths.index(
        "/academic-affairs/status-changes/{changeId}"
    )


def test_d3_permission_dependencies_remain_exact():
    review_codes = {
        "academicAffairs.statusChange.counselorReview",
        "academicAffairs.statusChange.collegeReview",
        "academicAffairs.statusChange.officeReview",
    }
    expected = {
        ("/academic-affairs/status-changes", "POST"): {"academicAffairs.statusChange.apply"},
        ("/academic-affairs/status-changes", "GET"): {
            "academicAffairs.statusChange.view",
            *review_codes,
        },
        ("/academic-affairs/status-changes/stats", "GET"): {"academicAffairs.statusChange.view"},
        ("/academic-affairs/status-changes/{changeId}", "GET"): {
            "academicAffairs.statusChange.view",
            *review_codes,
        },
        ("/academic-affairs/status-changes/{changeId}/review", "POST"): review_codes,
        ("/academic-affairs/status-changes/scheduled", "POST"): {"academicAffairs.statusChange.apply"},
    }
    for key, codes in expected.items():
        route = _first_route(*key)
        assert _permission_codes(route) == codes, (key, _permission_codes(route), codes)


def test_d3_routes_are_visible_in_final_openapi():
    from app.core.config import settings
    from app.main import app

    schema = app.openapi()
    for child in status_change_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        public_path = f"{settings.API_V1_PREFIX}{child.path}"
        assert public_path in schema["paths"], public_path
        for method in _methods(child):
            assert method.lower() in schema["paths"][public_path], (method, public_path)

    scheduled = f"{settings.API_V1_PREFIX}/academic-affairs/status-changes/scheduled"
    assert scheduled in schema["paths"]
    assert "post" in schema["paths"][scheduled]


def test_d3_move_only_reuses_legacy_contract_objects():
    from app.modules.academic_affairs.routers import academic_affairs as legacy

    assert status_change_router.StatusChangeSubmit is legacy.StatusChangeSubmit
    assert status_change_router.AaReviewBody is legacy.AaReviewBody
    assert status_change_router.change_svc is legacy.change_svc
    assert status_change_router._SC_LIST_VIEW is legacy._SC_LIST_VIEW
    assert status_change_router._SC_REVIEW_ANY is legacy._SC_REVIEW_ANY
