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


def test_agreement_pdf_route_is_registered_once() -> None:
    router = APIRouter()
    register_internship_routes(router, build_deps())

    path = "/internship/agreements/{agreement_id}/pdf"
    routes = _post_routes(router, path)
    assert len(routes) == 1, f"expected exactly one POST {path}, got {len(routes)}"
    assert routes[0].endpoint.__module__.endswith("internship_agreement_document")
