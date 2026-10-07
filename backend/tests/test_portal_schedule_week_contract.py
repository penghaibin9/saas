"""学生 PC 按周课表与打印查询件沿用同一正式学生课表投影。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import AppException
from app.core.security import get_current_user
from app.student_portal.services import academic_service as academic
from app.student_portal import router as portal_router


def test_portal_schedule_passes_optional_week_to_canonical_projection(monkeypatch):
    calls = []
    monkeypatch.setattr(academic.aa, "schedule_my", lambda user, week=None: calls.append((user, week)) or {"week": week, "items": []})
    user = {"userId": "student"}

    assert academic.schedule(user)["week"] is None
    assert academic.schedule(user, 6)["week"] == 6
    assert calls == [(user, None), (user, 6)]
    assert portal_router.academic_schedule(user=user, week=6)["data"]["week"] == 6


def test_portal_schedule_print_reads_requested_week_before_recording_audit(monkeypatch):
    calls = []
    monkeypatch.setattr(academic.aa, "schedule_my", lambda user, week=None: calls.append(("schedule", week)) or {"week": week, "items": [{"itemId": "new"}]})
    monkeypatch.setattr(academic.common, "print_log", lambda user, body: calls.append(("audit", body["bizType"])) or {"loggedAt": "now"})

    result = academic.schedule_print({"userId": "student", "userType": "STUDENT"}, {"week": 6, "reason": "第6周"})
    assert result["document"]["week"] == 6
    assert result["document"]["items"] == [{"itemId": "new"}]
    assert calls == [("schedule", 6), ("audit", "SCHEDULE")]


@pytest.mark.parametrize("week", [0, -1, 100, True, "6.5", ""])
def test_portal_schedule_print_rejects_unbounded_or_invalid_week_before_read(monkeypatch, week):
    monkeypatch.setattr(academic.aa, "schedule_my", lambda user, week=None: pytest.fail("无效周次不得读取课表"))
    with pytest.raises(AppException):
        academic.schedule_print({"userType": "STUDENT"}, {"week": week})


@pytest.mark.parametrize("query, expected_week", [("", None), ("?week=1", 1), ("?week=6", 6), ("?week=99", 99)])
def test_portal_schedule_http_preserves_optional_week_validation(monkeypatch, query, expected_week):
    calls = []
    user = {"userId": "student"}
    monkeypatch.setattr(academic, "schedule", lambda actor, week=None: calls.append((actor, week)) or {"week": week, "items": []})
    app = FastAPI()
    app.add_api_route("/schedule", portal_router.academic_schedule, methods=["GET"])
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        response = client.get("/schedule" + query)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["week"] == expected_week
    assert calls == [(user, expected_week)]


@pytest.mark.parametrize("week", ["0", "-1", "100", "true", "6.5", ""])
def test_portal_schedule_http_rejects_invalid_week_before_service(monkeypatch, week):
    monkeypatch.setattr(academic, "schedule", lambda *args, **kwargs: pytest.fail("无效周次不得读取课表"))
    app = FastAPI()
    app.add_api_route("/schedule", portal_router.academic_schedule, methods=["GET"])
    app.dependency_overrides[get_current_user] = lambda: {"userId": "student"}
    with TestClient(app) as client:
        response = client.get("/schedule", params={"week": week})
    assert response.status_code == 422, response.text
