"""消息中心收件面回归：已读≠确认、本人可见、批量已读、权限码。"""
from __future__ import annotations

MAIN = 1000000000000000001
CA_UID, CB_UID = 61001, 61002


def _token(user_id, login_name, role="COUNSELOR", user_type="TEACHER", tenant_id=MAIN):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u_{user_id}", "loginName": login_name, "realName": f"姓名{user_id}",
        "userType": user_type, "tid": "demo", "tenantId": str(tenant_id),
        "activeContextId": "ctx-a", "currentRoleCode": role, "clientType": "PC"})}


def _seed(_db_mode):
    from app.db.session import get_sessionmaker
    from app.models import UnifiedMessage
    db = get_sessionmaker()()
    try:
        db.add_all([
            UnifiedMessage(
                tenant_id=MAIN, receiver_id=CA_UID, receiver_user_id=CA_UID,
                receiver_context_key="GLOBAL", title="A全局未读", content="c1",
                message_type="ANNOUNCEMENT", category="ANNOUNCEMENT", status="UNREAD",
                require_ack=False),
            UnifiedMessage(
                tenant_id=MAIN, receiver_id=CA_UID, receiver_user_id=CA_UID,
                receiver_context_key="GLOBAL", title="A紧急待确认", content="c2",
                message_type="EMERGENCY", category="EMERGENCY", priority="EMERGENCY",
                status="UNREAD", require_ack=True),
            UnifiedMessage(
                tenant_id=MAIN, receiver_id=CA_UID, receiver_user_id=CA_UID,
                receiver_context_key="ctx-other", title="其他身份消息", content="c3",
                message_type="SYSTEM", category="SYSTEM", status="UNREAD"),
            UnifiedMessage(
                tenant_id=MAIN, receiver_id=CB_UID, receiver_user_id=CB_UID,
                receiver_context_key="GLOBAL", title="B的消息", content="c4",
                message_type="ANNOUNCEMENT", status="UNREAD"),
            # 历史兼容：仅 receiver_id=user_id
            UnifiedMessage(
                tenant_id=MAIN, receiver_id=CA_UID, title="A旧格式消息", content="legacy",
                message_type="SYSTEM", status="UNREAD"),
        ])
        db.commit()
    finally:
        db.close()


def test_inbox_scope_and_count(client, db_mode):
    _seed(db_mode)
    h = _token(CA_UID, "counselorA")
    r = client.get("/api/v1/admin/messages", headers=h).json()
    assert r["code"] == 0, r
    titles = [x["title"] for x in r["data"]["items"]]
    assert "A全局未读" in titles
    assert "A紧急待确认" in titles
    assert "A旧格式消息" in titles
    assert "B的消息" not in titles
    assert "其他身份消息" not in titles  # 激活身份不匹配

    cnt = client.get("/api/v1/admin/messages/count", headers=h).json()
    assert cnt["code"] == 0
    assert cnt["data"]["unread"] >= 3
    assert cnt["data"]["pendingAck"] >= 1


def test_detail_does_not_auto_read(client, db_mode):
    _seed(db_mode)
    h = _token(CA_UID, "counselorA")
    lst = client.get("/api/v1/admin/messages", headers=h).json()
    mid = next(x["messageId"] for x in lst["data"]["items"] if x["title"] == "A全局未读")
    d = client.get(f"/api/v1/admin/messages/{mid}", headers=h).json()
    assert d["code"] == 0
    assert d["data"]["readStatus"] == "UNREAD"
    assert "content" in d["data"] or "contentPlain" in d["data"]


def test_read_all_does_not_ack(client, db_mode):
    _seed(db_mode)
    h = _token(CA_UID, "counselorA")
    lst = client.get("/api/v1/admin/messages", headers=h).json()
    emerg = next(x for x in lst["data"]["items"] if x["title"] == "A紧急待确认")
    mid = emerg["messageId"]

    ra = client.post("/api/v1/admin/messages/read-all", headers=h).json()
    assert ra["code"] == 0
    assert ra["data"]["affectedCount"] >= 1

    d = client.get(f"/api/v1/admin/messages/{mid}", headers=h).json()
    assert d["data"]["readStatus"] == "READ"
    assert d["data"]["acked"] is False

    ack = client.post(f"/api/v1/admin/messages/{mid}/receipt", headers=h).json()
    assert ack["code"] == 0
    assert ack["data"]["acked"] is True

    d2 = client.get(f"/api/v1/admin/messages/{mid}", headers=h).json()
    assert d2["data"]["acked"] is True


def test_cross_user_404(client, db_mode):
    _seed(db_mode)
    ha = _token(CA_UID, "counselorA")
    hb = _token(CB_UID, "counselorB")
    lst = client.get("/api/v1/admin/messages", headers=ha).json()
    mid = lst["data"]["items"][0]["messageId"]
    r = client.get(f"/api/v1/admin/messages/{mid}", headers=hb).json()
    assert r["code"] != 0
