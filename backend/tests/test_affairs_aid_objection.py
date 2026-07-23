"""13A-C 困难认定公示异议端到端（真实 DB）。

覆盖：对公示中申请提异议→复核成立(驳回申请)/不成立(维持)；非公示不可提异议、
理由/意见校验、已复核不可再核。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_apply(sid, status="PUBLICITY"):
    from app.db.session import get_sessionmaker
    from app.models import AidApply, AidBatch
    db = get_sessionmaker()()
    b = AidBatch(tenant_id=TID, batch_name="2026困难认定", year_code="2025-2026", status="PUBLICITY")
    db.add(b); db.flush()
    x = AidApply(tenant_id=TID, batch_id=b.id, student_id=sid, apply_level="DIFFICULT",
                 final_level="DIFFICULT", status=status)
    db.add(x); db.commit()
    aid_ = x.id
    db.close()
    return aid_


def test_objection_sustained_rejects_apply(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    apply_id = _seed_apply(db_mode["student"], "PUBLICITY")
    # 理由过短
    r0 = client.post(f"{BASE}/aid/applications/{apply_id}/objection", headers=hdr, json={"reason": "短"})
    assert r0.status_code == 422 or r0.json().get("code") not in (0, None)
    # 提异议
    o = client.post(f"{BASE}/aid/applications/{apply_id}/objection", headers=hdr,
                    json={"reason": "该生家庭经济情况与申报不符", "objectorName": "同班同学"}).json()
    assert o["code"] == 0 and o["data"]["status"] == "SUBMITTED"
    oid = o["data"]["objectionId"]
    # 列表
    assert any(x["objectionId"] == oid for x in client.get(f"{BASE}/aid/objections", headers=hdr).json()["data"]["items"])
    # 复核成立 → 申请驳回
    rv = client.post(f"{BASE}/aid/objections/{oid}/review", headers=hdr,
                     json={"result": "SUSTAINED", "opinion": "核实异议属实，取消其困难认定资格"}).json()
    assert rv["code"] == 0 and rv["data"]["result"] == "SUSTAINED"
    detail = client.get(f"{BASE}/aid/applications/{apply_id}", headers=hdr).json()["data"]
    assert detail["status"] == "REJECTED"
    # 已复核不可再核
    assert client.post(f"{BASE}/aid/objections/{oid}/review", headers=hdr,
                       json={"result": "OVERRULED", "opinion": "再次复核维持原状"}).json()["code"] != 0


def test_objection_blocks_publicity_confirm(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    apply_id = _seed_apply(db_mode["student"], "PUBLICITY")
    from app.db.session import get_sessionmaker
    from app.models import AidApply
    from datetime import datetime, timedelta
    db = get_sessionmaker()()
    x = db.get(AidApply, apply_id)
    x.publicity_at = datetime.utcnow() - timedelta(days=1)
    db.commit(); db.close()
    o = client.post(f"{BASE}/aid/applications/{apply_id}/objection", headers=hdr,
                    json={"reason": "该生家庭经济情况与申报不符"}).json()
    assert o["code"] == 0
    blocked = client.post(f"{BASE}/aid/applications/{apply_id}/publicity-confirm", headers=hdr, json={}).json()
    assert blocked["code"] != 0
    detail = client.get(f"{BASE}/aid/applications/{apply_id}", headers=hdr).json()["data"]
    assert detail["status"] == "PUBLICITY"
    assert detail.get("hasPendingObjection") is True


def test_objection_overruled_and_non_publicity(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    apply_id = _seed_apply(db_mode["student"], "PUBLICITY")
    o = client.post(f"{BASE}/aid/applications/{apply_id}/objection", headers=hdr,
                    json={"reason": "对认定结果有疑问请复核"}).json()["data"]["objectionId"]
    rv = client.post(f"{BASE}/aid/objections/{o}/review", headers=hdr,
                     json={"result": "OVERRULED", "opinion": "经复核认定无误，异议不成立维持"}).json()
    assert rv["code"] == 0 and rv["data"]["result"] == "OVERRULED"
    detail = client.get(f"{BASE}/aid/applications/{apply_id}", headers=hdr).json()["data"]
    assert detail["status"] == "PUBLICITY"
    ap2 = _seed_apply(db_mode["student"], "CLASS_REVIEW")
    assert client.post(f"{BASE}/aid/applications/{ap2}/objection", headers=hdr,
                       json={"reason": "评议阶段不应可提异议"}).json()["code"] != 0
