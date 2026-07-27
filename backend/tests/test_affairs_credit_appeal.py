"""13A-D 第二课堂积分申诉端到端（真实 DB）。

覆盖：提交缺记申诉→审核通过(补记 MANUAL_ADJUST 学分,入二课台账)/驳回；
理由/意见/主张校验、已审核不可再核。
"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_credit_appeal_approve_creates_credit(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    # 理由过短
    r0 = client.post(f"{BASE}/second-class/appeals", headers=hdr,
                     json={"studentId": sid, "reason": "短", "claimValue": 2})
    assert r0.status_code == 422 or r0.json().get("code") not in (0, None)
    # 提交缺记申诉
    a = client.post(f"{BASE}/second-class/appeals", headers=hdr, json={
        "studentId": sid, "appealType": "MISSING", "claimCreditType": "SECOND_CLASS",
        "claimValue": 2, "reason": "参加校运会未记二课学时，申请补记"}).json()
    assert a["code"] == 0 and a["data"]["status"] == "SUBMITTED"
    aid = a["data"]["appealId"]
    # 列表
    assert any(x["appealId"] == aid for x in client.get(f"{BASE}/second-class/appeals", headers=hdr).json()["data"]["items"])
    # 审核通过 → 生成 MANUAL_ADJUST 学分
    r = post_versioned(client, f"{BASE}/second-class/appeals/{aid}/review", headers=hdr, json={"action": "APPROVE"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "APPROVED"
    led = client.get(f"{BASE}/second-class/ledger", headers=hdr).json()
    assert any(x["studentId"] == str(sid) and x["source"] == "MANUAL_ADJUST" for x in led["data"]["items"])
    # 已审核不可再核
    assert post_versioned(client, f"{BASE}/second-class/appeals/{aid}/review", headers=hdr,
                       json={"action": "REJECT", "opinion": "重复处理测试"}).json()["code"] != 0


def test_credit_appeal_reject(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    aid = client.post(f"{BASE}/second-class/appeals", headers=hdr, json={
        "studentId": sid, "claimValue": 1, "reason": "主张记错学时申请核减"}).json()["data"]["appealId"]
    # 驳回意见过短
    assert post_versioned(client, f"{BASE}/second-class/appeals/{aid}/review", headers=hdr,
                       json={"action": "REJECT", "opinion": "短"}).json()["code"] != 0
    # 正常驳回
    r = post_versioned(client, f"{BASE}/second-class/appeals/{aid}/review", headers=hdr,
                    json={"action": "REJECT", "opinion": "经核实原记录无误，驳回申诉"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "REJECTED"
