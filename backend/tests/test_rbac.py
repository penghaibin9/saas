"""P0 基线测试：RBAC 菜单/权限、租户品牌。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _token() -> str:
    return client.post("/api/v1/auth/mock-login", json={}).json()["data"]["accessToken"]


def test_rbac_menus():
    resp = client.get("/api/v1/rbac/menus", headers={"Authorization": f"Bearer {_token()}"})
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"]["items"], list)


def test_rbac_permissions():
    resp = client.get("/api/v1/rbac/permissions", headers={"Authorization": f"Bearer {_token()}"})
    assert resp.status_code == 200
    assert "buttons" in resp.json()["data"]


def test_rbac_data_scope():
    resp = client.get("/api/v1/rbac/data-scope", headers={"Authorization": f"Bearer {_token()}"})
    assert resp.status_code == 200
    assert len(resp.json()["data"]["catalog"]) == 12


def test_tenant_brand_returns_platform_name():
    resp = client.get("/api/v1/tenant/brand")
    assert resp.status_code == 200
    assert resp.json()["data"]["platformName"]
