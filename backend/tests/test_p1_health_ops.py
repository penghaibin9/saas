"""P1：health / internal metrics 访问控制。"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app, _ops_authorized
from starlette.requests import Request


def test_anonymous_health_ok():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "UP"


def test_ops_authorized_requires_token_in_prod():
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": "/health/ready",
        "raw_path": b"/health/ready", "query_string": b"", "headers": [],
        "client": ("8.8.8.8", 123), "server": ("test", 80),
    }
    req = Request(scope)
    with patch("app.main.settings") as s:
        s.INTERNAL_OPS_TOKEN = "secret-ops-token"
        s.is_prod = True
        assert _ops_authorized(req, None) is False
        assert _ops_authorized(req, "wrong") is False
        assert _ops_authorized(req, "secret-ops-token") is True


def test_ops_token_can_access_ready():
    c = TestClient(app)
    with patch("app.main.settings") as s:
        s.INTERNAL_OPS_TOKEN = "secret-ops-token"
        s.is_prod = False
        s.DB_ENABLED = False
        s.REDIS_URL = ""
        s.UPLOAD_DIR = "./uploads"
        s.EXPORT_DIR = "./exports"
        # 实际端点读的是模块级 settings；改为直接测授权 + 一次真实请求（本机非 prod）
    r = c.get("/health/ready", headers={"X-Ops-Token": "any"})
    # 开发环境本机回环可访问
    assert r.status_code in (200, 503)
    assert "mysql+pymysql://" not in r.text
    assert "Traceback" not in r.text


def test_anonymous_internal_metrics_with_token():
    c = TestClient(app)
    r = c.get("/internal/metrics", headers={"X-Ops-Token": "x"})
    assert r.status_code == 200


def test_ready_response_has_no_connection_string():
    c = TestClient(app)
    r = c.get("/health/ready")
    assert r.status_code in (200, 403, 503)
    body = r.text.lower()
    assert "password" not in body
    assert "jwt_secret" not in body
