from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.api.v1.route_registration import build_deps, register_internship_routes


def _post_routes(router: APIRouter, path: str) -> list[APIRoute]:
    return [
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and "POST" in (route.methods or set())
    ]


def test_guardian_consent_delivery_routes_are_registered_once() -> None:
    # Use the domain registration function directly so this structural unit test is
    # independent from tests/conftest.py's intentionally DB-disabled app bootstrap.
    # S5 separately probes the already-running final-RC backend over HTTP and requires
    # these paths to return an auth denial rather than 404.
    router = APIRouter()
    register_internship_routes(router, build_deps())

    expected = (
        "/internship/compliance/consents/deliver",
        "/internship/compliance/consents/{consent_id}/redeliver",
    )
    for path in expected:
        routes = _post_routes(router, path)
        assert len(routes) == 1, f"expected exactly one POST {path}, got {len(routes)}"
        assert routes[0].endpoint.__module__.endswith("internship_guardian_consent_delivery")
