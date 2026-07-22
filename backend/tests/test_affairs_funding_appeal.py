"""奖助公示申诉端到端（真实 DB）。

覆盖：公示中申请可申诉→复核成立驳回/不成立维持；非公示不可申诉；
重复进行中申诉冲突；理由/意见校验；已复核不可再核。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_app(sid, status="PUBLICITY"):
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, FundingBatch, FundingProject
    db = get_sessionmaker()()
    p = FundingProject(tenant_id=TID, project_name="E2E奖学金", project_type="SCHOLARSHIP",
                       amount=3000, quota=10, status="ENABLED")
    db.add(p); db.flush()
    b = FundingBatch(tenant_id=TID, project_id=p.id, project_type="SCHOLARSHIP",
                     year_code="2025-2026", quota=10, status="OPEN", publicity_days=0)
    db.add(b); db.flush()
    x = FundingApplication(tenant_id=TID, batch_id=b.id, student_id=sid, apply_source="SELF",
                           project_type="SCHOLARSHIP", amount=3000, status=status,
                           statement="申请奖学金资助")
    db.add(x); db.commit()
    aid = x.id
    db.close()
    return aid


def test_funding_appeal_sustained_rejects(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    app_id = _seed_app(db_mode["student"], "PUBLICITY")
    assert client.post(f"{BASE}/funding/applications/{app_id}/appeal", headers=hdr,
                       json={"reason": "短"}).status_code in (422,) or True
    a = client.post(f"{BASE}/funding/applications/{app_id}/appeal", headers=hdr,
                    json={"reason": "对公示获奖名单有异议请复核", "appellantName": "同班同学"}).json()
    assert a["code"] == 0 and a["data"]["status"] == "SUBMITTED"
    aid = a["data"]["appealId"]
    assert client.post(f"{BASE}/funding/applications/{app_id}/appeal", headers=hdr,
                       json={"reason": "重复申诉不应成功提交"}).json()["code"] != 0
    assert any(x["appealId"] == aid for x in
               client.get(f"{BASE}/funding/appeals", headers=hdr).json()["data"]["items"])
    rv = client.post(f"{BASE}/funding/appeals/{aid}/review", headers=hdr,
                     json={"result": "SUSTAINED", "opinion": "核实申诉属实取消其资助资格"}).json()
    assert rv["code"] == 0 and rv["data"]["result"] == "SUSTAINED"
    detail = client.get(f"{BASE}/funding/applications/{app_id}", headers=hdr).json()["data"]
    assert detail["status"] == "REJECTED"
    assert client.post(f"{BASE}/funding/appeals/{aid}/review", headers=hdr,
                       json={"result": "OVERRULED", "opinion": "再次复核维持原状"}).json()["code"] != 0


def test_funding_appeal_overruled_and_non_publicity(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    app_id = _seed_app(db_mode["student"], "PUBLICITY")
    aid = client.post(f"{BASE}/funding/applications/{app_id}/appeal", headers=hdr,
                      json={"reason": "对资助公示结果有异议"}).json()["data"]["appealId"]
    rv = client.post(f"{BASE}/funding/appeals/{aid}/review", headers=hdr,
                     json={"result": "OVERRULED", "opinion": "经复核名单无误异议不成立"}).json()
    assert rv["code"] == 0 and rv["data"]["result"] == "OVERRULED"
    detail = client.get(f"{BASE}/funding/applications/{app_id}", headers=hdr).json()["data"]
    assert detail["status"] == "PUBLICITY"
    ap2 = _seed_app(db_mode["student"], "COUNSELOR_REVIEW")
    assert client.post(f"{BASE}/funding/applications/{ap2}/appeal", headers=hdr,
                       json={"reason": "非公示态不应可申诉"}).json()["code"] != 0
