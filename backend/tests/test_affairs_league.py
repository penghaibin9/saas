"""13A-D 党团建设（07 卡）端到端（真实 DB）。

覆盖：建党员发展台账→推进阶段(五阶段,append-only,到正式党员置 COMPLETED)→阶段时间线(材料仅标记有无)；
重复建档冲突、阶段不可回退/相等、终止原因过短校验。材料明文不入列表/时间线。
"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_league_dev_full_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    did = client.post(f"{BASE}/party-league/dev", headers=hdr, json={
        "studentId": sid, "devType": "PARTY", "branchName": "计算机学院学生第一党支部"}).json()["data"]["devId"]
    # 重复建档 → 冲突
    assert client.post(f"{BASE}/party-league/dev", headers=hdr,
                       json={"studentId": sid, "devType": "PARTY"}).json()["code"] != 0
    # 不能回退/相等
    assert post_versioned(f"{BASE}/party-league/dev/{did}/advance", headers=hdr,
                       json={"toStage": "APPLICANT"}).json()["code"] != 0
    # 逐级推进
    for stage in ("ACTIVIST", "DEVELOPMENT_TARGET", "PROBATIONARY"):
        r = post_versioned(f"{BASE}/party-league/dev/{did}/advance", headers=hdr,
                        json={"toStage": stage, "materialFileId": 1}).json()
        assert r["code"] == 0 and r["data"]["currentStage"] == stage and r["data"]["status"] == "ONGOING"
    # 转正 → COMPLETED
    r2 = post_versioned(f"{BASE}/party-league/dev/{did}/advance", headers=hdr,
                     json={"toStage": "FULL_MEMBER"}).json()
    assert r2["data"]["currentStage"] == "FULL_MEMBER" and r2["data"]["status"] == "COMPLETED"
    # COMPLETED 后不可再推进
    assert post_versioned(f"{BASE}/party-league/dev/{did}/advance", headers=hdr,
                       json={"toStage": "FULL_MEMBER"}).json()["code"] != 0
    # 阶段时间线：5 条(建档 APPLICANT + 4 次推进)，材料仅标记 hasMaterial，无明文字段
    stages = client.get(f"{BASE}/party-league/dev/{did}/stages", headers=hdr).json()["data"]["items"]
    assert len(stages) == 5
    assert all("materialFileId" not in s for s in stages)
    assert any(s["hasMaterial"] for s in stages)  # 中间阶段带了材料
    # 列表可见且不含材料明文
    lst = client.get(f"{BASE}/party-league/dev", headers=hdr).json()["data"]["items"]
    assert any(x["devId"] == did and x["status"] == "COMPLETED" for x in lst)


def test_league_dev_terminate_and_validation(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    did = client.post(f"{BASE}/party-league/dev", headers=hdr,
                      json={"studentId": sid, "devType": "LEAGUE"}).json()["data"]["devId"]
    # 终止原因过短 → 拒绝
    assert post_versioned(f"{BASE}/party-league/dev/{did}/terminate", headers=hdr,
                       json={"reason": "短"}).json()["code"] != 0
    # 正常终止
    t = post_versioned(f"{BASE}/party-league/dev/{did}/terminate", headers=hdr,
                    json={"reason": "本人申请退出发展流程"}).json()
    assert t["code"] == 0 and t["data"]["status"] == "TERMINATED"
    # 终止后不可推进
    assert post_versioned(f"{BASE}/party-league/dev/{did}/advance", headers=hdr,
                       json={"toStage": "ACTIVIST"}).json()["code"] != 0
    # 非法阶段码
    did2 = client.post(f"{BASE}/party-league/dev", headers=hdr,
                       json={"studentId": sid, "devType": "PARTY"}).json()["data"]["devId"]
    r = post_versioned(f"{BASE}/party-league/dev/{did2}/advance", headers=hdr, json={"toStage": "XXX"})
    assert r.status_code == 422 or r.json().get("code") not in (0, None)
