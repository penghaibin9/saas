from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_standalone_baseline():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["product"] == "internship-standalone"
    assert body["sourceBaseline"] == "adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c"
