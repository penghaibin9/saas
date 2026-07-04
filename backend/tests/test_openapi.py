"""P0 基线测试：OpenAPI schema 与 /docs 可用性。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_openapi_schema_generated():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "paths" in schema
    assert "/health" in schema["paths"]
    assert "/api/v1/auth/mock-login" in schema["paths"]


def test_docs_page_available():
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
