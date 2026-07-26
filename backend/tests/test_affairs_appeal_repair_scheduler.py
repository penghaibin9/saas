"""异议/申诉补偿定时触发目标测试。"""
from __future__ import annotations


def test_periodic_affairs_scans_are_wrapped_for_appeal_repair():
    from app.services import affairs_counselor_service, affairs_leave_service, affairs_risk_service

    assert getattr(affairs_leave_service.scan_overdue, "_affairs_appeal_repair_scheduled", False)
    assert getattr(affairs_risk_service.scan_timeout, "_affairs_appeal_repair_scheduled", False)
    assert getattr(affairs_counselor_service.scan_expired_temps, "_affairs_appeal_repair_scheduled", False)


def test_run_due_executes_persisted_repair_queue(monkeypatch):
    from app.services import affairs_appeal_repair_scheduler as scheduler
    from app.services import affairs_appeal_repair_service as repair

    calls = []

    def fake_repair_pending(limit=20):
        calls.append(limit)
        return {"claimed": 3, "repaired": 2, "failed": 1}

    monkeypatch.setattr(repair, "repair_pending", fake_repair_pending)
    result = scheduler.run_due(force=True)

    assert calls == [100]
    assert result == {
        "skipped": False,
        "claimed": 3,
        "repaired": 2,
        "failed": 1,
    }


def test_scheduled_repair_failure_does_not_break_other_periodic_jobs(monkeypatch):
    from app.services import affairs_appeal_repair_scheduler as scheduler
    from app.services import affairs_appeal_repair_service as repair

    def broken_repair(limit=20):
        raise RuntimeError("repair unavailable")

    monkeypatch.setattr(repair, "repair_pending", broken_repair)
    result = scheduler.run_due(force=True)

    assert result["failed"] == 1
    assert result["errorType"] == "RuntimeError"
