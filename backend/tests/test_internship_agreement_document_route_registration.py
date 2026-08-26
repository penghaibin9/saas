from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.api.v1.route_registration import build_deps, register_internship_routes
from app.modules.internship.routers import internship_agreement_document


def _post_routes(router: APIRouter, path: str) -> list[APIRoute]:
    return [
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and "POST" in (route.methods or set())
    ]


def _route_snapshot(router: APIRouter) -> list[tuple[str, str, tuple[str, ...]]]:
    return [
        (
            type(route).__name__,
            str(getattr(route, "path", "")),
            tuple(sorted(getattr(route, "methods", None) or set())),
        )
        for route in router.routes
    ]


def test_agreement_pdf_route_is_registered_once() -> None:
    path = "/internship/agreements/{agreement_id}/pdf"

    child_routes = _post_routes(internship_agreement_document.router, path)
    assert len(child_routes) == 1, (
        f"agreement document child router must expose exactly one POST {path}; "
        f"child_routes={_route_snapshot(internship_agreement_document.router)}"
    )

    router = APIRouter()
    register_internship_routes(router, build_deps())

    routes = _post_routes(router, path)
    assert len(routes) == 1, (
        f"expected exactly one registered POST {path}, got {len(routes)}; "
        f"registered_agreement_routes="
        f"{[item for item in _route_snapshot(router) if 'agreement' in item[1] or 'pdf' in item[1]]}"
    )
    assert routes[0].endpoint.__module__.endswith("internship_agreement_document")
