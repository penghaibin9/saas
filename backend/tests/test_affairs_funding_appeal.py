"""奖助公示申诉安全收口：进行中申诉拦截获资助、范围/租户/唯一约束。"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

from datetime import datetime, timedelta

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_app(sid, status="PUBLICITY", publicity_days=0):
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, FundingBatch, FundingProject
    db = get_sessionmaker()()
    p = FundingProject(tenant_id=TID, project_name="拦截测奖学金", project_type="SCHOLARSHIP",
                       amount=3000, quota=10, status="ENABLED")
    db.add(p); db.flush()
    b = FundingBatch(tenant_id=TID, project_id=p.id, project_type="SCHOLARSHIP",
                     year_code="2025-2026", quota=10, status="OPEN", publicity_days=publicity_days)
    db.add(b); db.flush()
    x = FundingApplication(tenant_id=TID, batch_id=b.id, student_id=sid, apply_source="SELF",
                           project_type="SCHOLARSHIP", amount=3000, status=status,
                           statement="申请奖学金资助",
                           publicity_at=datetime.utcnow() - timedelta(days=1))
    db.add(x); db.commit()
    aid = x.id
    db.close()
    ensure_workflow_assignees(sid, nodes=("SCHOOL_REVIEW",))
    return aid


def test_funding_appeal_blocks_publicity_confirm_and_scan(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    app_id = _seed_app(db_mode["student"], "PUBLICITY", publicity_days=0)
    a = post_versioned(f"{BASE}/funding/applications/{app_id}/appeal", headers=hdr,
                    json={"reason": "对公示获奖名单有异议请复核"}).json()
    assert a["code"] == 0
    # 人工确认应被拦
    blocked = post_versioned(f"{BASE}/funding/applications/{app_id}/publicity-confirm", headers=hdr, json={}).json()
    assert blocked["code"] != 0
    # 扫描应跳过
    scanned = client.post(f"{BASE}/funding/scan-publicity", headers=hdr, json={}).json()
    assert scanned["code"] == 0
    assert (scanned["data"] or {}).get("count", 0) == 0
    assert (scanned["data"] or {}).get("skippedAppeal", 0) >= 1
    detail = client.get(f"{BASE}/funding/applications/{app_id}", headers=hdr).json()["data"]
    assert detail["status"] == "PUBLICITY"
    assert detail["hasPendingAppeal"] is True
    # 复核成立 → 驳回 + 通知字段
    aid = a["data"]["appealId"]
    rv = post_versioned(f"{BASE}/funding/appeals/{aid}/review", headers=hdr,
                     json={"result": "SUSTAINED", "opinion": "核实申诉属实取消其资助资格"}).json()
    assert rv["code"] == 0
    detail2 = client.get(f"{BASE}/funding/applications/{app_id}", headers=hdr).json()["data"]
    assert detail2["status"] == "REJECTED"
    assert detail2.get("returnReason")


def test_funding_appeal_sustained_rejects(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    app_id = _seed_app(db_mode["student"], "PUBLICITY")
    a = post_versioned(f"{BASE}/funding/applications/{app_id}/appeal", headers=hdr,
                    json={"reason": "对公示获奖名单有异议请复核", "appellantName": "同班同学"}).json()
    assert a["code"] == 0 and a["data"]["status"] == "SUBMITTED"
    aid = a["data"]["appealId"]
    assert post_versioned(f"{BASE}/funding/applications/{app_id}/appeal", headers=hdr,
                       json={"reason": "重复申诉不应成功提交"}).json()["code"] != 0
    assert any(x["appealId"] == aid for x in
               client.get(f"{BASE}/funding/appeals", headers=hdr).json()["data"]["items"])
    rv = post_versioned(f"{BASE}/funding/appeals/{aid}/review", headers=hdr,
                     json={"result": "SUSTAINED", "opinion": "核实申诉属实取消其资助资格"}).json()
    assert rv["code"] == 0 and rv["data"]["result"] == "SUSTAINED"
    detail = client.get(f"{BASE}/funding/applications/{app_id}", headers=hdr).json()["data"]
    assert detail["status"] == "REJECTED"
    assert post_versioned(f"{BASE}/funding/appeals/{aid}/review", headers=hdr,
                       json={"result": "OVERRULED", "opinion": "再次复核维持原状"}).json()["code"] != 0


def test_funding_appeal_overruled_and_non_publicity(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    app_id = _seed_app(db_mode["student"], "PUBLICITY")
    aid = post_versioned(f"{BASE}/funding/applications/{app_id}/appeal", headers=hdr,
                      json={"reason": "对资助公示结果有异议"}).json()["data"]["appealId"]
    rv = post_versioned(f"{BASE}/funding/appeals/{aid}/review", headers=hdr,
                     json={"result": "OVERRULED", "opinion": "经复核名单无误异议不成立"}).json()
    assert rv["code"] == 0 and rv["data"]["result"] == "OVERRULED"
    detail = client.get(f"{BASE}/funding/applications/{app_id}", headers=hdr).json()["data"]
    assert detail["status"] == "PUBLICITY"
    ap2 = _seed_app(db_mode["student"], "COUNSELOR_REVIEW")
    assert post_versioned(f"{BASE}/funding/applications/{ap2}/appeal", headers=hdr,
                       json={"reason": "非公示态不应可申诉"}).json()["code"] != 0
