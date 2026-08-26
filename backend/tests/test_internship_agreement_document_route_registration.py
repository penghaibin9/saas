from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.api.v1.route_registration import build_deps, register_internship_routes
from app.modules.internship.routers import internship_agreement_document


PDF_PATH = "/internship/agreements/{agreement_id}/pdf"


def _post_routes(router: APIRouter, path: str = PDF_PATH) -> list[APIRoute]:
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


class RecordingRouter(APIRouter):
    def __init__(self) -> None:
        super().__init__()
        self.document_include_calls: list[dict[str, object]] = []

    def include_router(self, router: APIRouter, **kwargs) -> None:
        is_document = router is internship_agreement_document.router
        before = len(self.routes)
        result = super().include_router(router, **kwargs)
        if is_document:
            self.document_include_calls.append(
                {
                    "childPrefix": router.prefix,
                    "childRoutes": _route_snapshot(router),
                    "parentBefore": before,
                    "parentAfter": len(self.routes),
                    "pdfAfterInclude": len(_post_routes(self)),
                }
            )
        return result


def test_agreement_pdf_route_is_registered_once() -> None:
    child_routes = _post_routes(internship_agreement_document.router)
    assert len(child_routes) == 1, (
        f"agreement document child router must expose exactly one POST {PDF_PATH}; "
        f"child_routes={_route_snapshot(internship_agreement_document.router)}"
    )

    # FastAPI control: prove this exact child router can be included directly.
    direct = APIRouter()
    direct.include_router(internship_agreement_document.router, dependencies=build_deps()["intern"])
    assert len(_post_routes(direct)) == 1, (
        "direct include of agreement document router failed; "
        f"direct_routes={_route_snapshot(direct)}"
    )

    router = RecordingRouter()
    register_internship_routes(router, build_deps())

    routes = _post_routes(router)
    assert len(routes) == 1, (
        f"expected exactly one registered POST {PDF_PATH}, got {len(routes)}; "
        f"document_include_calls={router.document_include_calls}; "
        f"registered_agreement_routes="
        f"{[item for item in _route_snapshot(router) if 'agreement' in item[1] or 'pdf' in item[1]]}"
    )
    assert routes[0].endpoint.__module__.endswith("internship_agreement_document")
