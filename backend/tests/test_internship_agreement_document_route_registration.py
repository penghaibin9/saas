from fastapi import APIRouter, FastAPI

from app.api.v1.route_registration import build_deps, register_internship_routes


PDF_PATH = "/api/v1/internship/agreements/{agreement_id}/pdf"


def test_agreement_pdf_route_is_registered_once() -> None:
    """Assert the route from the final FastAPI routing/OpenAPI surface.

    FastAPI >= 0.137 preserves included routers as lazy ``_IncludedRouter``
    nodes instead of flattening child ``APIRoute`` objects into ``router.routes``.
    The production contract is therefore the effective application route, not
    the first-level implementation detail of ``APIRouter.routes``.
    """
    api_router = APIRouter()
    register_internship_routes(api_router, build_deps())

    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

    paths = app.openapi().get("paths", {})
    operation = paths.get(PDF_PATH, {}).get("post")
    assert operation is not None, (
        f"missing effective POST {PDF_PATH}; "
        f"agreement_paths={sorted(path for path in paths if 'agreement' in path or 'pdf' in path)}"
    )

    operation_id = str(operation.get("operationId") or "")
    assert "agreement_pdf" in operation_id, (
        f"POST {PDF_PATH} resolved to unexpected operationId={operation_id!r}"
    )
