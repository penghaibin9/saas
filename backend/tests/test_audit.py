"""审计日志：真实业务动作产生审计 + logs 可查询。

注意：此前这里用 /api/v1/audit/mock-record 造记录。那个接口已删除——
审计表不应该对外提供"往里塞一条假记录"的入口，否则审计就不是证据。
现在改为触发真实被审计的业务动作（登出）再断言可查。
"""
from __future__ import annotations


def test_audit_record_and_query(client, auth_headers):
    assert client.post("/api/v1/authz/logout", headers=auth_headers).json()["code"] == 0
    body = client.get("/api/v1/audit/logs?action=LOGOUT", headers=auth_headers).json()
    assert body["code"] == 0
    assert body["data"]["total"] >= 1


def test_mock_record_endpoint_is_gone(client, auth_headers):
    """回归锁：不许有人把"写假审计"的联调接口加回来。"""
    assert client.post("/api/v1/audit/mock-record", headers=auth_headers).status_code == 404
