"""学工异议/申诉补偿 external worker 目标测试。"""
from __future__ import annotations


def test_external_worker_once_calls_all_tenant_repair(monkeypatch):
    from app import affairs_appeal_repair_worker as worker

    monkeypatch.setattr(worker, "db_enabled", lambda: True)
    monkeypatch.setattr(worker, "run_all_tenants", lambda: {
        "tenants": 2, "claimed": 3, "repaired": 3, "failed": 0, "skipped": 0,
    })

    assert worker.run_once() == {
        "tenants": 2, "claimed": 3, "repaired": 3, "failed": 0, "skipped": 0,
    }


def test_external_worker_refuses_to_run_without_database(monkeypatch):
    import pytest
    from app import affairs_appeal_repair_worker as worker

    monkeypatch.setattr(worker, "db_enabled", lambda: False)
    with pytest.raises(RuntimeError, match="DB_ENABLED=true"):
        worker.run_once()


def test_external_worker_once_cli_exits_successfully(monkeypatch):
    from app import affairs_appeal_repair_worker as worker

    calls = []
    monkeypatch.setattr(worker, "run_once", lambda: calls.append(True) or {})
    assert worker.main(["--once"]) == 0
    assert calls == [True]
