from fastapi import APIRouter, FastAPI

from app.api.v1.route_registration import build_deps, register_internship_routes


DELIVER_PATH = "/api/v1/internship/compliance/consents/deliver"
REDELIVER_PATH = "/api/v1/internship/compliance/consents/{consent_id}/redeliver"


def test_guardian_consent_delivery_routes_are_registered_once() -> None:
    """Assert guardian delivery routes from the final FastAPI/OpenAPI surface.

    FastAPI >= 0.137 keeps included routers as lazy ``_IncludedRouter`` nodes,
    so first-level ``APIRouter.routes`` is not the production routing contract.
    The effective application/OpenAPI surface is the authoritative route table.
    """
    api_router = APIRouter()
    register_internship_routes(api_router, build_deps())

    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

    paths = app.openapi().get("paths", {})
    deliver = paths.get(DELIVER_PATH, {}).get("post")
    redeliver = paths.get(REDELIVER_PATH, {}).get("post")

    assert deliver is not None, (
        f"missing effective POST {DELIVER_PATH}; "
        f"consent_paths={sorted(path for path in paths if 'consent' in path)}"
    )
    assert redeliver is not None, (
        f"missing effective POST {REDELIVER_PATH}; "
        f"consent_paths={sorted(path for path in paths if 'consent' in path)}"
    )

    assert "create_and_deliver" in str(deliver.get("operationId") or "")
    assert "redeliver" in str(redeliver.get("operationId") or "")
