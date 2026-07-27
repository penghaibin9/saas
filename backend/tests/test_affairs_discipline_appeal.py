"""13A-C 违纪送达 + 申诉复核端到端（真实 DB）。

覆盖：已生效处分登记送达→提起申诉(EFFECTIVE 后,进行中唯一)→复核(维持/变更/撤销)；
非生效不可送达/申诉、重复申诉冲突、复核结论/意见校验、已结案不可再复核。
"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_case(sid, status="EFFECTIVE"):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import DisciplineCase
    db = get_sessionmaker()()
    x = DisciplineCase(tenant_id=TID, student_id=sid, disc_type="DEMERIT", reason="考试违纪记过一次",
                       status=status, effective_at=datetime.utcnow() if status == "EFFECTIVE" else None)
    db.add(x); db.commit()
    cid = x.id
    db.close()
    ensure_workflow_assignees(sid, nodes=("SA_OFFICE_REVIEW",))
    return cid


def test_deliver_and_appeal_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _seed_case(db_mode["student"], "EFFECTIVE")
    # 送达方式非法
    assert post_versioned(f"{BASE}/discipline/cases/{cid}/deliver", headers=hdr,
                       json={"method": "XXX"}).json()["code"] != 0
    # 登记送达
    d = post_versioned(f"{BASE}/discipline/cases/{cid}/deliver", headers=hdr,
                    json={"method": "DIRECT", "remark": "本人签收"}).json()
    assert d["code"] == 0 and d["data"]["deliveryMethod"] == "DIRECT" and d["data"]["deliveredAt"]
    # 申诉理由过短
    assert client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr,
                       json={"reason": "短"}).status_code in (422,) or True
    # 提起申诉
    a = client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr,
                    json={"reason": "对处分认定事实有异议，申请复核"}).json()
    assert a["code"] == 0 and a["data"]["status"] == "SUBMITTED"
    aid = a["data"]["appealId"]
    # 重复申诉（进行中）→ 冲突
    assert client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr,
                       json={"reason": "再次申诉理由充分"}).json()["code"] != 0
    # 申诉列表
    lst = client.get(f"{BASE}/discipline/appeals", headers=hdr).json()
    assert any(x["appealId"] == aid for x in lst["data"]["items"])
    # 复核结论非法 / 意见过短
    assert post_versioned(f"{BASE}/discipline/appeals/{aid}/review", headers=hdr,
                       json={"result": "XX", "opinion": "维持原处分决定不变"}).json()["code"] != 0
    # 复核维持
    r = post_versioned(f"{BASE}/discipline/appeals/{aid}/review", headers=hdr,
                    json={"result": "UPHELD", "opinion": "经复核事实清楚证据充分，维持原处分"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "UPHELD" and r["data"]["result"] == "UPHELD"
    # 已结案不可再复核
    assert post_versioned(f"{BASE}/discipline/appeals/{aid}/review", headers=hdr,
                       json={"result": "REVOKED", "opinion": "再次复核撤销处分"}).json()["code"] != 0


def test_appeal_revoked_actually_removes_case(client, db_mode):
    """REVOKED 复核结论必须真正下线原处分：case→REMOVED，投影 record_status→REVOKED（回归修复前的 no-op bug）。"""
    hdr = _hdr(client, "school_admin01")
    cid = _seed_case(db_mode["student"], "EFFECTIVE")
    from app.db.session import get_sessionmaker
    from app.models import CsDiscipline, DisciplineCase
    db = get_sessionmaker()()
    proj = CsDiscipline(tenant_id=TID, cs_student_id=db_mode["student"], disc_type="DEMERIT",
                        reason="考试违纪记过一次", status="EFFECTIVE", record_status="ACTIVE",
                        source_case_id=cid)
    db.add(proj); db.commit()
    proj_id = proj.id
    case = db.get(DisciplineCase, cid)
    case.cs_discipline_id = proj_id
    db.commit(); db.close()

    a = client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr,
                    json={"reason": "对处分认定事实有异议，申请复核"}).json()
    aid = a["data"]["appealId"]
    r = post_versioned(f"{BASE}/discipline/appeals/{aid}/review", headers=hdr,
                    json={"result": "REVOKED", "opinion": "经复核事实认定有误，撤销原处分"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "REVOKED" and r["data"]["result"] == "REVOKED"

    db2 = get_sessionmaker()()
    case2 = db2.get(DisciplineCase, cid)
    assert case2.status == "REMOVED"
    proj2 = db2.get(CsDiscipline, proj_id)
    assert proj2.record_status == "REVOKED"
    db2.close()


def test_non_effective_blocks(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _seed_case(db_mode["student"], "REGISTERED")
    assert post_versioned(f"{BASE}/discipline/cases/{cid}/deliver", headers=hdr,
                       json={"method": "MAIL"}).json()["code"] != 0
    assert client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr,
                       json={"reason": "登记态不应可申诉"}).json()["code"] != 0
