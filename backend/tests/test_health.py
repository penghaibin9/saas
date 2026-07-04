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
