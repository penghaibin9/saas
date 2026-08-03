"""学工异议/申诉补偿 external worker 目标测试。"""
from __future__ import annotations


def test_external_worker_once_bootstraps_contracts_then_repairs_all_tenants(monkeypatch):
    from app import affairs_appeal_repair_worker as worker

    calls = []
    monkeypatch.setattr(worker, "db_enabled", lambda: True)
    monkeypatch.setattr(worker, "_ensure_contracts_installed", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(worker, "run_all_tenants", lambda: calls.append("repair") or {
        "tenants": 2, "claimed": 3, "repaired": 3, "failed": 0, "skipped": 0,
    })

    assert worker.run_once() == {
        "tenants": 2, "claimed": 3, "repaired": 3, "failed": 0, "skipped": 0,
    }
    assert calls == ["bootstrap", "repair"]


def test_external_worker_refuses_to_run_without_database(monkeypatch):
    import pytest
    from app import affairs_appeal_repair_worker as worker

    monkeypatch.setattr(worker, "db_enabled", lambda: False)
    with pytest.raises(RuntimeError, match="DB_ENABLED=true"):
        worker.run_once()


def test_external_worker_recovers_bindings_without_router_import(monkeypatch):
    from app import affairs_appeal_repair_worker as worker
    from app.services import affairs_appeal_repair_service as repair

    monkeypatch.setattr(repair, "_RAW_SYNC", None)
    monkeypatch.setattr(repair, "_RAW_NOTICE", None)
    worker._ensure_contracts_installed()
    assert repair._RAW_SYNC is not None
    assert repair._RAW_NOTICE is not None


def test_external_worker_once_cli_exits_successfully(monkeypatch):
    from app import affairs_appeal_repair_worker as worker

    calls = []
    monkeypatch.setattr(worker, "run_once", lambda: calls.append(True) or {})
    assert worker.main(["--once"]) == 0
    assert calls == [True]
