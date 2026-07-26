"""异议/申诉补偿定时触发目标测试。"""
from __future__ import annotations

import inspect


def test_periodic_affairs_scans_are_wrapped_for_appeal_repair():
    from app.services import affairs_counselor_service, affairs_leave_service, affairs_risk_service

    assert getattr(affairs_leave_service.scan_overdue, "_affairs_appeal_repair_scheduled", False)
    assert getattr(affairs_risk_service.scan_timeout, "_affairs_appeal_repair_scheduled", False)
    assert getattr(affairs_counselor_service.scan_expired_temps, "_affairs_appeal_repair_scheduled", False)


def test_default_web_scheduler_enables_all_wrapped_affairs_scans():
    from app.core.config import Settings
    from app import main

    source = inspect.getsource(main.lifespan)
    assert Settings.model_fields["AFFAIRS_LEAVE_OVERDUE_AUTO_SCAN"].default is True
    assert Settings.model_fields["AFFAIRS_RISK_TIMEOUT_AUTO_SCAN"].default is True
    assert Settings.model_fields["AFFAIRS_COUNSELOR_TEMP_AUTO_SCAN"].default is True
    assert "affairs_leave_service.scan_overdue()" in source
    assert "affairs_risk_service.scan_timeout()" in source
    assert "affairs_counselor_service.scan_expired_temps()" in source


def test_run_due_executes_persisted_repair_queue(monkeypatch):
    from app.services import affairs_appeal_repair_scheduler as scheduler
    from app.services import affairs_appeal_repair_service as repair

    calls = []

    def fake_repair_pending(limit=20):
        calls.append(limit)
        return {"claimed": 3, "repaired": 2, "failed": 1}

    monkeypatch.setattr(repair, "repair_pending", fake_repair_pending)
    monkeypatch.setattr(scheduler, "_tenant_key", lambda: "tenant-1")
    result = scheduler.run_due(force=True)

    assert calls == [100]
    assert result == {
        "tenantId": "tenant-1",
        "skipped": False,
        "claimed": 3,
        "repaired": 2,
        "failed": 1,
    }


def test_repair_throttle_is_isolated_per_tenant(monkeypatch):
    from app.services import affairs_appeal_repair_scheduler as scheduler
    from app.services import affairs_appeal_repair_service as repair

    current = {"key": "tenant-a"}
    calls = []
    monkeypatch.setattr(scheduler, "_tenant_key", lambda: current["key"])
    monkeypatch.setattr(repair, "repair_pending", lambda limit=20: calls.append(current["key"]) or {
        "claimed": 0, "repaired": 0, "failed": 0,
    })
    scheduler._LAST_RUN_AT.clear()

    assert scheduler.run_due()["skipped"] is False
    assert scheduler.run_due()["skipped"] is True
    current["key"] = "tenant-b"
    assert scheduler.run_due()["skipped"] is False
    assert calls == ["tenant-a", "tenant-b"]


def test_scheduled_repair_failure_does_not_break_other_periodic_jobs(monkeypatch):
    from app.services import affairs_appeal_repair_scheduler as scheduler
    from app.services import affairs_appeal_repair_service as repair

    def broken_repair(limit=20):
        raise RuntimeError("repair unavailable")

    monkeypatch.setattr(repair, "repair_pending", broken_repair)
    monkeypatch.setattr(scheduler, "_tenant_key", lambda: "tenant-error")
    result = scheduler.run_due(force=True)

    assert result["tenantId"] == "tenant-error"
    assert result["failed"] == 1
    assert result["errorType"] == "RuntimeError"
