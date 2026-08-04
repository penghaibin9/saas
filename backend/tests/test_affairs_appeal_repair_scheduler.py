"""异议/申诉补偿显式调度目标测试。"""
from __future__ import annotations

import inspect


def test_router_no_longer_installs_periodic_monkey_patch():
    from app.api.v1 import router

    source = inspect.getsource(router)
    assert "install_appeal_repair_scheduler" not in source
    assert "install_appeal_repair" not in source


def test_web_scheduler_calls_repair_and_async_export_explicitly():
    from app import main

    source = inspect.getsource(main.lifespan)
    assert "affairs_appeal_repair_service.repair_pending" in source
    assert "affairs_leave_export_service.run_pending" in source
    assert 'name="student-affairs-background"' in source


def test_external_scheduler_calls_repair_and_async_export_explicitly():
    from scripts import run_scheduled_jobs

    source = inspect.getsource(run_scheduled_jobs.job_student_affairs_background)
    assert "repair.repair_pending" in source
    assert "leave_export.run_pending" in source
    assert "TRIAL" in inspect.getsource(run_scheduled_jobs._schedulable_tenant_ids)


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
        "tenantId": "tenant-1", "skipped": False,
        "claimed": 3, "repaired": 2, "failed": 1,
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
