"""审计日志：mock-record 写入 + logs 可查询。"""
from __future__ import annotations


def test_audit_record_and_query(client, auth_headers):
    assert client.post("/api/v1/audit/mock-record", headers=auth_headers).json()["code"] == 0
    body = client.get("/api/v1/audit/logs", headers=auth_headers).json()
    assert body["code"] == 0
    assert body["data"]["total"] >= 1
