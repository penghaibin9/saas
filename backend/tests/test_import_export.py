"""导入导出占位（非生产）与真实权限门禁冒烟。"""
from __future__ import annotations


def test_import_validate_placeholder(client, auth_headers):
    body = client.post("/api/v1/import/validate-placeholder", headers=auth_headers,
                       json={"bizType": "student", "rows": [{"studentNo": "1"}]}).json()
    assert body["code"] == 0


def test_export_placeholder_task_unknown_is_404(client, auth_headers):
    """未知 taskId 不得再伪造 SUCCESS，避免泄露/猜测。"""
    task = client.get("/api/v1/export/tasks/exp-demo", headers=auth_headers)
    assert task.status_code == 404
