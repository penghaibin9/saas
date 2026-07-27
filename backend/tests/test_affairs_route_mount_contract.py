from fastapi import APIRouter
from fastapi.routing import APIRoute


def _signature(route):
    return route.path, frozenset(route.methods or ())


def test_supplemental_routes_mount_with_path_and_method():
    from app.api.v1.affairs_activity_mobile import router as activity_router
    from app.api.v1.affairs_appeal_mobile import router as appeal_router
    from app.api.v1.affairs_appeal_repair_api import router as repair_router
    from app.api.v1.affairs_four_end import router as four_end_router
    from app.api.v1.router import _mount_supplemental_router

    parent = APIRouter()
    for child in (four_end_router, activity_router, appeal_router, repair_router):
        _mount_supplemental_router(parent, child)

    mounted = {
        _signature(route)
        for route in parent.routes
        if isinstance(route, APIRoute)
    }
    expected = {
        ("/mobile/teacher/affairs/student-candidates", frozenset({"GET"})),
        ("/mobile/teacher/affairs/activities/ongoing", frozenset({"GET"})),
        ("/mobile/teacher/affairs/activities/{activity_id}/checkin-token", frozenset({"GET"})),
        ("/mobile/teacher/affairs/appeals/{kind}", frozenset({"GET"})),
        ("/mobile/teacher/affairs/appeals/{kind}/{appeal_id}/review", frozenset({"POST"})),
        ("/mobile/teacher/affairs/appeals/repair", frozenset({"POST"})),
    }
    assert expected <= mounted


def test_supplemental_route_mount_is_idempotent():
    from app.api.v1.affairs_four_end import router as child
    from app.api.v1.router import _mount_supplemental_router

    parent = APIRouter()
    _mount_supplemental_router(parent, child)
    first = [_signature(route) for route in parent.routes if isinstance(route, APIRoute)]
    _mount_supplemental_router(parent, child)
    second = [_signature(route) for route in parent.routes if isinstance(route, APIRoute)]
    assert second == first
