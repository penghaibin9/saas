from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import build_teacher_mobile_router
from app.core.exceptions import register_exception_handlers


def _app():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(build_teacher_mobile_router(), prefix="/api/v1")
    return app


def test_teacher_mobile_internship_surface_is_mounted():
    paths = set(_app().openapi().get("paths", {}))
    assert "/api/v1/mobile/teacher/internship/context" in paths
    assert "/api/v1/mobile/teacher/internship/context/applications" in paths
    assert "/api/v1/mobile/teacher/internship/context/applications/summary" in paths
    assert "/api/v1/mobile/teacher/internship/context/applications/students" in paths


def test_teacher_mobile_internship_surface_is_not_public():
    client = TestClient(_app())
    assert client.get("/api/v1/mobile/teacher/internship/context").status_code == 401
    assert client.get(
        "/api/v1/mobile/teacher/internship/context/applications/summary",
        params={"batchId": "1"},
    ).status_code == 401
