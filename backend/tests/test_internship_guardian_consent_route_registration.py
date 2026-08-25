from fastapi.routing import APIRoute

from app.api.v1.router import api_router


def _post_routes(path: str) -> list[APIRoute]:
    return [
        route
        for route in api_router.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and "POST" in (route.methods or set())
    ]


def test_guardian_consent_delivery_routes_are_registered_once() -> None:
    expected = (
        "/internship/compliance/consents/deliver",
        "/internship/compliance/consents/{consent_id}/redeliver",
    )
    for path in expected:
        routes = _post_routes(path)
        assert len(routes) == 1, f"expected exactly one POST {path}, got {len(routes)}"
        assert routes[0].endpoint.__module__.endswith("internship_guardian_consent_delivery")
