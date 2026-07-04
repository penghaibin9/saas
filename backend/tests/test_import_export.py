"""导入导出占位。"""
from __future__ import annotations


def test_import_validate_placeholder(client, auth_headers):
    body = client.post("/api/v1/import/validate-placeholder", headers=auth_headers,
                       json={"bizType": "student", "rows": [{"studentNo": "1"}]}).json()
    assert body["code"] == 0


def test_export_placeholder_and_task(client, auth_headers):
    body = client.post("/api/v1/export/create-placeholder", headers=auth_headers,
                       json={"bizType": "student", "purpose": "学院例会名单核对"}).json()
    assert body["code"] == 0
    task = client.get("/api/v1/export/tasks/exp-demo", headers=auth_headers).json()
    assert task["code"] == 0
    assert "审计" in task["data"]["securityNotice"]
