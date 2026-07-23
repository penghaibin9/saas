"""P3 回归：审计列表与互查路由可达。"""
from __future__ import annotations


def test_graduation_audit_logs_list(client, auth_headers, db_mode):
    r = client.get("/api/v1/graduation/audit-logs", headers=auth_headers, params={"page": 1, "pageSize": 10}).json()
    assert r["code"] == 0
    data = r["data"]
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_mobile_peer_tasks_requires_student(client, auth_headers, db_mode):
    r = client.get("/api/v1/mobile/graduation/peer-tasks", headers=auth_headers).json()
    # 管理端 token 不是学生身份，应拒绝
    assert r["code"] in (403001, 401001)
