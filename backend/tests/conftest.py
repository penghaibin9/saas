"""pytest 公共夹具：默认 DB_ENABLED=false（mock 模式），共享 TestClient 与登录令牌。"""
from __future__ import annotations

import os

os.environ.setdefault("DB_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def auth_headers(client: TestClient) -> dict:
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}
