"""13A-D 学生干部与组织（06 卡）端到端（真实 DB）。

覆盖：建组织→任命(唯一防重复)→在任列表→干部履历(含组织任职)→卸任；同名组织/空职务校验。
"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_org_full_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    oid = client.post(f"{BASE}/organizations", headers=hdr, json={
        "orgName": "校学生会", "orgType": "STUDENT_UNION", "level": "SCHOOL"}).json()["data"]["orgId"]
    # 同名 → 冲突
    assert client.post(f"{BASE}/organizations", headers=hdr, json={"orgName": "校学生会"}).json()["code"] != 0
    # 任命
    pid = client.post(f"{BASE}/organizations/{oid}/positions", headers=hdr,
                      json={"studentId": sid, "position": "主席", "termCode": "2025-2026"}).json()["data"]["positionId"]
    # 重复同职 → 冲突
    assert client.post(f"{BASE}/organizations/{oid}/positions", headers=hdr,
                       json={"studentId": sid, "position": "主席"}).json()["code"] != 0
    # 在任列表
    pos = client.get(f"{BASE}/organizations/{oid}/positions", headers=hdr).json()
    assert len(pos["data"]["items"]) == 1 and pos["data"]["items"][0]["position"] == "主席"
    # 干部履历含该任职
    res = client.get(f"{BASE}/students/{sid}/cadre-resume", headers=hdr).json()
    assert any(r["source"] == "ORG" and r["position"] == "主席" for r in res["data"]["items"])
    # 卸任
    assert post_versioned(client, f"{BASE}/organizations/positions/{pid}/dismiss", headers=hdr).json()["code"] == 0
    pos2 = client.get(f"{BASE}/organizations/{oid}/positions", headers=hdr).json()
    assert len(pos2["data"]["items"]) == 0
    # 卸任后可重新任命同职（唯一约束仅约束 ACTIVE）
    assert client.post(f"{BASE}/organizations/{oid}/positions", headers=hdr,
                       json={"studentId": sid, "position": "主席"}).json()["code"] == 0


def test_org_validation(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/organizations", headers=hdr, json={"orgName": ""})
    assert r.status_code == 422 or r.json().get("code") not in (0, None)
    oid = client.post(f"{BASE}/organizations", headers=hdr,
                      json={"orgName": "院学生会", "level": "COLLEGE"}).json()["data"]["orgId"]
    # 空职务 → 拒绝
    r2 = client.post(f"{BASE}/organizations/{oid}/positions", headers=hdr,
                     json={"studentId": db_mode["student"], "position": ""})
    assert r2.status_code == 422 or r2.json().get("code") not in (0, None)
