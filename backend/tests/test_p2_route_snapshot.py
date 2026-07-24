"""路由快照：拆分注册后端点可达、生产不挂占位路由。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_core_api_prefixes_reachable():
    c = TestClient(app)
    # 未登录应 401，说明路由存在（非 404）
    for path in (
        "/api/v1/auth/login",
        "/api/v1/system/info",
        "/api/v1/files",
        "/api/v1/student-affairs/leave/scan-overdue",
        "/api/v1/academic-affairs/dashboard",
        "/api/v1/internship/stats/overview",
        "/api/v1/graduation/batches",
        "/api/v1/platform/tenants",
    ):
        r = c.get(path) if path != "/api/v1/auth/login" else c.post(path, json={})
        assert r.status_code != 404, path


def test_health_and_internal_present():
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert c.get("/internal/metrics").status_code in (200, 403)


def test_production_placeholder_gated_in_source():
    from app.api.v1 import route_registration as rr
    src = open(rr.__file__, encoding="utf-8").read()
    assert "if not settings.is_prod" in src
    assert "placeholder_router" in src
