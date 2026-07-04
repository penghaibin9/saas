"""P0 基线测试：mock 登录 / 当前用户 / 切换身份。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_mock_login_returns_user_and_token():
    resp = client.post("/api/v1/auth/mock-login", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0 and body["bizCode"] == "SUCCESS"
    data = body["data"]
    assert data["accessToken"]
    assert data["user"]["realName"]
    assert data["contexts"]


def test_me_with_token():
    login = client.post("/api/v1/auth/mock-login", json={}).json()["data"]
    token = login["accessToken"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["userId"]


def test_me_without_token_is_unauthorized():
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == 401001 and resp.json()["bizCode"] == "UNAUTHORIZED"
