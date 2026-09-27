from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.router import build_staff_internship_router


def _app():
    app = FastAPI()
    app.include_router(build_staff_internship_router(), prefix="/api/v1")
    return app


def test_w2_staff_openapi_has_core_routes():
    paths = set(_app().openapi().get("paths", {}))
    assert "/api/v1/internship/students" in paths
    assert "/api/v1/internship/enterprises" in paths
    assert "/api/v1/internship/positions" in paths
    assert "/api/v1/internship/applications" in paths
    assert len(paths) >= 80, len(paths)


def test_w2_staff_routes_have_no_duplicate_method_path():
    signatures = set()
    duplicates = []
    for route in _app().routes:
        if not isinstance(route, APIRoute):
            continue
        for method in (route.methods or set()) - {"HEAD", "OPTIONS"}:
            sig = (method, route.path)
            if sig in signatures:
                duplicates.append(sig)
            signatures.add(sig)
    assert not duplicates, duplicates


def test_w2_staff_routes_keep_staff_and_module_gates():
    routes = [
        route for route in _app().routes
        if isinstance(route, APIRoute) and route.path.startswith("/internship")
    ]
    assert routes
    assert all(len(route.dependant.dependencies) >= 2 for route in routes)
