"""13A-D 社团管理（05 卡）端到端（真实 DB）。

覆盖：建社→审批通过→增补成员(唯一防重复)→成员列表→年审(一社一年一条)→退社→注销；
同名社团/非运营态增补/重复年审/驳回原因过短等校验。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_club_full_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    cid = client.post(f"{BASE}/clubs", headers=hdr, json={
        "clubName": "动漫社", "clubType": "ARTS", "advisorName": "王老师"}).json()["data"]["clubId"]
    # 同名 → 冲突
    assert client.post(f"{BASE}/clubs", headers=hdr, json={"clubName": "动漫社"}).json()["code"] != 0
    # 未审批不能加成员
    assert client.post(f"{BASE}/clubs/{cid}/members", headers=hdr,
                       json={"studentId": sid}).json()["code"] != 0
    # 审批通过
    r = client.post(f"{BASE}/clubs/{cid}/review", headers=hdr, json={"action": "APPROVE"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "ACTIVE"
    # 加成员
    mid = client.post(f"{BASE}/clubs/{cid}/members", headers=hdr,
                      json={"studentId": sid, "role": "PRESIDENT"}).json()["data"]["memberId"]
    # 重复入社 → 冲突
    assert client.post(f"{BASE}/clubs/{cid}/members", headers=hdr,
                       json={"studentId": sid}).json()["code"] != 0
    # 成员列表 + member_count 同步
    mem = client.get(f"{BASE}/clubs/{cid}/members", headers=hdr).json()
    assert len(mem["data"]["items"]) == 1
    lst = client.get(f"{BASE}/clubs", headers=hdr).json()
    assert any(c["clubId"] == cid and c["memberCount"] == 1 for c in lst["data"]["items"])
    # 年审
    assert client.post(f"{BASE}/clubs/{cid}/annual-reviews", headers=hdr,
                       json={"reviewYear": "2025-2026", "result": "PASS", "activityCount": 8}).json()["code"] == 0
    # 重复年审 → 冲突
    assert client.post(f"{BASE}/clubs/{cid}/annual-reviews", headers=hdr,
                       json={"reviewYear": "2025-2026"}).json()["code"] != 0
    rv = client.get(f"{BASE}/clubs/{cid}/annual-reviews", headers=hdr).json()
    assert len(rv["data"]["items"]) == 1
    # 退社 → count 归零
    assert client.post(f"{BASE}/clubs/members/{mid}/remove", headers=hdr).json()["code"] == 0
    lst2 = client.get(f"{BASE}/clubs", headers=hdr).json()
    assert any(c["clubId"] == cid and c["memberCount"] == 0 for c in lst2["data"]["items"])
    # 注销原因过短 → 拒绝；正常注销
    assert client.post(f"{BASE}/clubs/{cid}/disband", headers=hdr, json={"reason": "短"}).json()["code"] != 0
    d = client.post(f"{BASE}/clubs/{cid}/disband", headers=hdr,
                    json={"reason": "社团连续两年未开展活动，按管理办法注销"}).json()
    assert d["code"] == 0 and d["data"]["status"] == "DISBANDED"


def test_club_validation(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    # 空名 → 422 或信封业务错
    r = client.post(f"{BASE}/clubs", headers=hdr, json={"clubName": ""})
    assert r.status_code == 422 or r.json().get("code") not in (0, None)
    # 非法类型
    assert client.post(f"{BASE}/clubs", headers=hdr,
                       json={"clubName": "测试社", "clubType": "XXX"}).json()["code"] != 0
