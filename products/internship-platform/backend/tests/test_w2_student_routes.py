from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.router import build_student_mobile_router, build_student_portal_router
from app.core.exceptions import AppException, register_exception_handlers
from app.core.security import require_mobile_student


def _app():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(build_student_mobile_router(), prefix="/api/v1")
    app.include_router(build_student_portal_router(), prefix="/api/v1")
    return app


def test_student_surfaces_are_mounted():
    paths = set(_app().openapi().get("paths", {}))
    assert "/api/v1/mobile/internship/context/my" in paths
    assert "/api/v1/mobile/internship/catalog/positions" in paths
    assert "/api/v1/portal/internship/compliance" in paths
    assert "/api/v1/portal/internship/catalog/positions" in paths


def test_student_surfaces_are_not_public():
    client = TestClient(_app())
    assert client.get("/api/v1/mobile/internship/context/my").status_code == 401
    assert client.get("/api/v1/portal/internship/compliance").status_code == 401


def test_mobile_student_gate_rejects_staff_identity():
    with pytest.raises(AppException) as exc:
        require_mobile_student({"userType": "TEACHER"})
    assert exc.value.code == "NO_PERMISSION"
