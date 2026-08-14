"""D6-S：选课域公开 route owner、唯一性与 Move Only canonical 合同。"""
from __future__ import annotations

import re

from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.routers import academic_affairs_bundle as bundle
from app.modules.academic_affairs.routers import academic_export_compat_router as export_compat
from app.modules.academic_affairs.routers import academic_selection_final_router as final_router
from app.modules.academic_affairs.routers import course_selection_router as selection_router


def _shape(route):
    path = re.sub(r"\{[^/{}]+\}", "{}", getattr(route, "path", ""))
    methods = tuple(sorted(getattr(route, "methods", set()) or set()))
    return path, methods


def _public_route(public, path: str, method: str):
    matches = [
        route
        for route in public.routes
        if getattr(route, "path", None) == path
        and method in (getattr(route, "methods", set()) or set())
    ]
    assert len(matches) == 1, f"expected one route for {method} {path}, got {len(matches)}"
    return matches[0]


def test_d6_selection_move_only_router_owns_non_final_surface():
    public = bundle.build_router()
    for route in selection_router.router.routes:
        method = next(iter(getattr(route, "methods", set()) or set()))
        endpoint = _public_route(public, route.path, method).endpoint
        assert endpoint.__module__ == selection_router.__name__


def test_d6_selection_final_and_export_routes_keep_existing_canonical_owners():
    public = bundle.build_router()
    final_shapes = {
        ("POST", "/academic-affairs/selection/batches/{batchId}/publish"),
        ("GET", "/academic-affairs/selection/student/courses"),
        ("POST", "/academic-affairs/selection/student/enroll"),
        ("POST", "/academic-affairs/selection/student/drop"),
    }
    for method, path in final_shapes:
        assert _public_route(public, path, method).endpoint.__module__ == final_router.__name__

    export_shapes = {
        ("POST", "/academic-affairs/selection/batches/{batchId}/conflict-report/export"),
        ("POST", "/academic-affairs/selection/archive/{batchId}/export"),
    }
    for method, path in export_shapes:
        assert _public_route(public, path, method).endpoint.__module__ == export_compat.__name__


def test_d6_selection_public_shapes_are_unique_after_split():
    public = bundle.build_router()
    shapes = [
        _shape(route)
        for route in public.routes
        if getattr(route, "path", "").startswith("/academic-affairs/selection/")
    ]
    assert len(shapes) == len(set(shapes))


def test_d6_selection_split_reuses_legacy_dto_permissions_and_services():
    assert selection_router.SelectionBatchBody is legacy.SelectionBatchBody
    assert selection_router.SelectionRuleBody is legacy.SelectionRuleBody
    assert selection_router.SelectionCourseBody is legacy.SelectionCourseBody
    assert selection_router.SelectionCourseUpdate is legacy.SelectionCourseUpdate
    assert selection_router.AdjustBody is legacy.AdjustBody
    assert selection_router.SelectionRoundBody is legacy.SelectionRoundBody
    assert selection_router.selection_svc is legacy.selection_svc
    assert selection_router.selection_round_svc is legacy.selection_round_svc
    assert selection_router._SEL_VIEW == legacy._SEL_VIEW
    assert selection_router._SEL_MANAGE == legacy._SEL_MANAGE
    assert selection_router._SEL_RULE == legacy._SEL_RULE
