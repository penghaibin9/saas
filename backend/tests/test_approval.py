"""审批任务第一批 API。"""
from __future__ import annotations


def test_tasks_list(client, auth_headers):
    body = client.get("/api/v1/approvals/tasks", headers=auth_headers).json()
    assert body["code"] == 0 and isinstance(body["data"]["items"], list)


def test_approve_task(client, auth_headers):
    body = client.post("/api/v1/approvals/tasks/at-1001/approve", headers=auth_headers,
                       json={"comment": "同意", "version": 0}).json()
    assert body["code"] == 0 and body["data"]["status"] == "APPROVED"


def test_reject_without_reason_fails(client, auth_headers):
    resp = client.post("/api/v1/approvals/tasks/at-1003/reject", headers=auth_headers,
                       json={"version": 0})
    assert resp.json()["code"] in (400001, 422001)


def test_reject_with_reason(client, auth_headers):
    body = client.post("/api/v1/approvals/tasks/at-1003/reject", headers=auth_headers,
                       json={"reason": "材料不清晰请重新上传", "version": 0}).json()
    assert body["code"] == 0 and body["data"]["status"] == "REJECTED"
