from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


def test_external_scheduler_registers_risk_timeout_job():
    source = _source("scripts/run_scheduled_jobs.py")

    assert "def job_risk_timeout()" in source
    assert "affairs_risk_service.scan_timeout()" in source
    assert "_Ticker(INTERVAL_LEAVE_OVERDUE, now0, job_risk_timeout)" in source


def test_web_scheduler_registers_risk_timeout_scan():
    source = _source("app/main.py")

    assert "AFFAIRS_RISK_TIMEOUT_AUTO_SCAN" in source
    assert "affairs_risk_service.scan_timeout()" in source
    assert 'name="affairs-risk-timeout-scan"' in source


def test_risk_timeout_settings_are_declared():
    source = _source("app/core/config.py")

    assert "AFFAIRS_RISK_TIMEOUT_AUTO_SCAN: bool = True" in source
    assert "AFFAIRS_RISK_NEW_ASSIGN_HOURS: float = 4" in source
    assert "AFFAIRS_RISK_ASSIGNED_PROCESS_HOURS: float = 72" in source
