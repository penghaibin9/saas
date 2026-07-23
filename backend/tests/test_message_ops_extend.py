"""消息中心运维/模板/对账冒烟。"""
from __future__ import annotations

MAIN = 1000000000000000001


def _admin_token():
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u_1", "loginName": "admin", "realName": "管理员",
        "userType": "TEACHER", "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})}


def test_ops_reconcile_and_dead_letters(client, db_mode):
    h = _admin_token()
    r = client.get("/api/v1/admin/message-campaigns/ops/reconcile", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True or body.get("code") in (0, "0", None) or "data" in body

    r2 = client.get("/api/v1/admin/message-campaigns/ops/dead-letters", headers=h)
    assert r2.status_code == 200


def test_template_create_toggle(client, db_mode):
    h = _admin_token()
    code = f"HUMAN_TPL_{MAIN % 10000}"
    r = client.post("/api/v1/admin/message-campaigns/templates", headers=h, json={
        "templateCode": code,
        "title": "人工发布模板",
        "content": "你好 {name}",
        "channel": "IN_APP",
        "enabled": True,
    })
    assert r.status_code == 200, r.text
    data = r.json().get("data") or {}
    tid = data.get("templateId")
    assert tid
    r2 = client.patch(f"/api/v1/admin/message-campaigns/templates/{tid}", headers=h, json={"enabled": False})
    assert r2.status_code == 200
    assert r2.json()["data"]["enabled"] is False
