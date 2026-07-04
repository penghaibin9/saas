"""阶段17：mock-login / me / 任务规定的 8 账号与扁平字段。"""
from __future__ import annotations


def test_mock_login_task_accounts(client):
    body = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "counselor01", "password": "x"}).json()
    assert body["code"] == 0
    d = body["data"]
    for key in ("userId", "username", "displayName", "tenantId", "tenantName",
                "currentRole", "roles", "dataScope", "permissionActions",
                "accessToken", "tokenType", "expiresIn"):
        assert key in d, f"missing {key}"
    assert d["username"] == "counselor01"


def test_me_ok(client, auth_headers):
    body = client.get("/api/v1/auth/me", headers=auth_headers).json()
    assert body["code"] == 0
    assert body["data"]["userId"]


def test_logout(client, auth_headers):
    body = client.post("/api/v1/auth/logout", headers=auth_headers).json()
    assert body["code"] == 0
