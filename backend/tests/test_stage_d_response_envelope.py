"""Stage D error envelope stays backward compatible while adding decisionTrace."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import AppException, register_exception_handlers


def test_app_exception_adds_top_level_decision_trace_without_breaking_legacy_fields():
    app = FastAPI()
    register_exception_handlers(app)
    trace = {
        "schemaVersion": "1.0",
        "traceId": "1f340b55-6c80-5346-860d-0140acfa4f56",
        "domain": "SELECTION",
        "action": "ENROLL",
        "decision": "DENIED",
        "ruleCode": "COURSE_FULL",
        "ruleVersion": None,
        "subject": {},
        "target": {"courseCode": "DB201"},
        "failedNodes": [],
        "passedNodes": [],
        "availableResolutions": [],
        "evaluatedAt": "2026-08-09T15:30:00",
    }

    @app.get("/decision-trace-contract")
    def endpoint():
        raise AppException(
            "DATA_CONFLICT",
            "课程容量已满",
            details={"legacy": "still-here"},
            http_status=409,
            decision_trace=trace,
        )

    response = TestClient(app).get("/decision-trace-contract")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == 409001
    assert body["bizCode"] == "DATA_CONFLICT"
    assert body["message"] == "课程容量已满"
    assert body["data"] is None
    assert body["details"] == {"legacy": "still-here"}
    assert body["decisionTrace"] == trace
    assert body["traceId"]
    assert body["timestamp"]


def test_app_exception_without_decision_trace_keeps_exact_old_shape_contract():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/legacy-error")
    def endpoint():
        raise AppException("DATA_CONFLICT", "旧错误", details={"x": 1}, http_status=409)

    body = TestClient(app).get("/legacy-error").json()
    assert body["code"] == 409001
    assert body["bizCode"] == "DATA_CONFLICT"
    assert body["message"] == "旧错误"
    assert body["details"] == {"x": 1}
    assert "decisionTrace" not in body
