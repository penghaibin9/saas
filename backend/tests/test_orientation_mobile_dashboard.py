"""Parameter contracts for the teacher orientation dashboard; no database fixture."""
import pytest

from app.services import _mobile_teacher_service_impl as mobile


TEACHER = {"userType": "TEACHER", "currentRoleCode": "STUDENT_AFFAIRS_ADMIN", "userId": "test-teacher"}


def test_mobile_dashboard_uses_same_batch_and_actor_for_pending_arrivals(monkeypatch):
    monkeypatch.setattr(mobile, "db_enabled", lambda: True)
    calls = []
    dashboard = {"batchId": "9007199254740993", "batchStatus": "ACTIVE", "batchName": "本轮迎新", "batchPeriod": "报到期间", "kpis": [{"key": "total", "value": "1"}]}

    def get_dashboard(**kwargs):
        calls.append(("dashboard", kwargs))
        return dashboard

    def list_students(*args, **kwargs):
        calls.append(("students", args, kwargs))
        return [{"id": "25", "reportStatus": "PREPARED"}], 1

    monkeypatch.setattr(mobile.orientation_service, "get_dashboard", get_dashboard)
    monkeypatch.setattr(mobile.orientation_service, "list_students", list_students)
    result = mobile.orientation_dashboard(TEACHER)
    assert calls == [
        ("dashboard", {"user": TEACHER}),
        ("students", (1, 30), {"batch_id": dashboard["batchId"], "pending_arrival": True, "user": TEACHER}),
    ]
    assert result["batchId"] == dashboard["batchId"]
    assert result["kpis"] == dashboard["kpis"]
    assert result["notReportedTotal"] == 1
    assert result["notReported"][0]["reportStatus"] == "PREPARED"


def test_mobile_dashboard_without_batch_never_queries_all_school_students(monkeypatch):
    monkeypatch.setattr(mobile, "db_enabled", lambda: True)
    monkeypatch.setattr(mobile.orientation_service, "get_dashboard", lambda **kwargs: {"batchId": ""})
    monkeypatch.setattr(mobile.orientation_service, "list_students", lambda *args, **kwargs: pytest.fail("Unscoped list must not run"))
    result = mobile.orientation_dashboard(TEACHER)
    assert result["hasData"] is False
    assert result["notReported"] == [] and result["notReportedTotal"] == 0


def test_mobile_dashboard_errors_remain_errors_instead_of_zero_arrivals(monkeypatch):
    monkeypatch.setattr(mobile, "db_enabled", lambda: True)
    monkeypatch.setattr(mobile.orientation_service, "get_dashboard", lambda **kwargs: {"batchId": "18", "batchStatus": "ACTIVE"})

    def failed_list(*args, **kwargs):
        raise RuntimeError("无法读取本批次名单")

    monkeypatch.setattr(mobile.orientation_service, "list_students", failed_list)
    with pytest.raises(RuntimeError, match="本批次名单"):
        mobile.orientation_dashboard(TEACHER)

@pytest.mark.parametrize("status", ["CLOSED", "DRAFT", "VOID", "", None])
def test_mobile_dashboard_non_active_batch_never_opens_pending_arrival_queue(monkeypatch, status):
    monkeypatch.setattr(mobile, "db_enabled", lambda: True)
    monkeypatch.setattr(mobile.orientation_service, "get_dashboard", lambda **kwargs: {"batchId": "18", "batchStatus": status})
    monkeypatch.setattr(mobile.orientation_service, "list_students", lambda *args, **kwargs: pytest.fail("Non-active queue must not run"))
    result = mobile.orientation_dashboard(TEACHER)
    assert result["hasData"] is False
    assert result["notReported"] == [] and result["notReportedTotal"] == 0
