"""P0 基线测试：/health 健康检查。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_body_shape():
    body = client.get("/health").json()
    assert body["code"] == 0 and body["bizCode"] == "SUCCESS"
    assert body["data"]["status"] == "UP"
    assert body["data"]["dbEnabled"] is False
    assert body["traceId"]
    assert body["timestamp"]


def test_health_metrics_has_latency_and_status_counts():
    body = client.get("/health/metrics").json()
    assert body["code"] == 0
    assert body["data"]["sampleSize"] >= 1
    assert "p95" in body["data"]["latencyMs"]
    assert "statuses" in body["data"]


def test_health_ready_audit_log_degrades_on_db_write_failure():
    """历史欠账收口回归：审计落库失败此前 except:pass 静默吞掉，现须在 /health/ready 可见。"""
    from app.core.config import settings
    from app.services import audit_log

    old_enabled = settings.DB_ENABLED
    old_health = dict(audit_log._DB_HEALTH)
    try:
        settings.DB_ENABLED = True
        audit_log._DB_HEALTH["consecutiveFailures"] = 0
        audit_log._DB_HEALTH["lastFailure"] = None
        healthy = client.get("/health/ready").json()["data"]["checks"]["auditLog"]
        assert healthy == {"ok": True}

        audit_log._DB_HEALTH["consecutiveFailures"] = 3
        audit_log._DB_HEALTH["lastFailure"] = {"occurredAt": "x", "action": "TEST", "error": "boom"}
        body = client.get("/health/ready").json()["data"]
        assert body["checks"]["auditLog"]["ok"] is False
        assert body["checks"]["auditLog"]["consecutiveFailures"] == 3
        assert body["status"] == "DEGRADED"
    finally:
        settings.DB_ENABLED = old_enabled
        audit_log._DB_HEALTH.clear()
        audit_log._DB_HEALTH.update(old_health)


def test_health_ready_file_scan_required_unhealthy_is_not_ready(monkeypatch):
    """正式附件扫描依赖不可用时不得返回 READY，避免附件全卡隔离区却假绿。"""
    from app.services import file_scan_service

    monkeypatch.setattr(file_scan_service, "health_snapshot", lambda: {
        "enabled": True,
        "required": True,
        "engineHealthy": False,
        "queueDepth": 2,
        "deadJobs": 0,
    })
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    data = resp.json()["data"]
    assert data["status"] == "DEGRADED"
    assert data["checks"]["fileScan"]["ok"] is False
    assert data["checks"]["fileScan"]["queueDepth"] == 2


def test_health_ready_file_scan_dead_job_is_not_ready(monkeypatch):
    """扫描任务进入 DEAD 代表人工处置前不能把试点环境判定为完全就绪。"""
    from app.services import file_scan_service

    monkeypatch.setattr(file_scan_service, "health_snapshot", lambda: {
        "enabled": True,
        "required": True,
        "engineHealthy": True,
        "queueDepth": 0,
        "deadJobs": 1,
    })
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    data = resp.json()["data"]
    assert data["checks"]["fileScan"]["ok"] is False
    assert data["checks"]["fileScan"]["deadJobs"] == 1
