"""13A-C 家校回执端到端（真实 DB）：全局家校列表 + 回执登记。"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_contact(sid):
    from app.db.session import get_sessionmaker
    from app.models import FamilyContactLog
    db = get_sessionmaker()()
    x = FamilyContactLog(tenant_id=TID, student_id=sid, contact_type="PHONE",
                         contact_reason="学业情况沟通", contact_result="家长知晰")
    db.add(x); db.commit()
    cid = x.id
    db.close()
    return cid


def test_family_receipt_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    cid = _seed_contact(sid)
    # 全局列表含该条，默认待回执
    listed = client.get(f"{BASE}/family-contacts", headers=hdr).json()["data"]
    lst = listed["items"]
    row = next(x for x in lst if x["contactId"] == str(cid))
    assert row["receiptStatus"] == "PENDING"
    assert listed["statusCounts"]["ALL"] >= 1
    assert listed["statusCounts"]["PENDING"] >= 1
    # 按待回执筛
    pend = client.get(f"{BASE}/family-contacts", headers=hdr, params={"receiptStatus": "PENDING"}).json()["data"]["items"]
    assert any(x["contactId"] == str(cid) for x in pend)
    # 登记回执
    r = client.post(f"{BASE}/family-contacts/{cid}/receipt", headers=hdr,
                    json={"note": "家长已回复知晰并配合"}).json()
    assert r["code"] == 0 and r["data"]["receiptStatus"] == "RECEIVED" and r["data"]["receiptAt"]
    # 重复回执 → 冲突
    assert client.post(f"{BASE}/family-contacts/{cid}/receipt", headers=hdr, json={"note": "x"}).json()["code"] != 0
    # 已回执筛得到
    received_data = client.get(
        f"{BASE}/family-contacts", headers=hdr, params={"receiptStatus": "RECEIVED"}
    ).json()["data"]
    recv = received_data["items"]
    assert any(x["contactId"] == str(cid) for x in recv)
    assert received_data["statusCounts"]["RECEIVED"] >= 1
