"""13A 奖助扩展端到端（真实 DB）：勤工助学 / 助学贷款 / 减免临补。"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_work_study_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    pid = client.post(f"{BASE}/work-study/posts", headers=hdr, json={
        "deptName": "图书馆", "postName": "书库整理员", "salary": 800, "headcount": 3}).json()["data"]["postId"]
    assert len(client.get(f"{BASE}/work-study/posts", headers=hdr).json()["data"]["items"]) >= 1
    # 申请
    rid = client.post(f"{BASE}/work-study/posts/{pid}/apply", headers=hdr, json={"studentId": sid}).json()["data"]["recordId"]
    # 重复申请冲突
    assert client.post(f"{BASE}/work-study/posts/{pid}/apply", headers=hdr, json={"studentId": sid}).json()["code"] != 0
    # 未录用不可上岗
    assert client.post(f"{BASE}/work-study/records/{rid}/action", headers=hdr, json={"action": "ONBOARD"}).json()["code"] != 0
    # 录用→上岗→终止
    assert client.post(f"{BASE}/work-study/records/{rid}/action", headers=hdr, json={"action": "APPROVE"}).json()["data"]["status"] == "APPROVED"
    assert client.post(f"{BASE}/work-study/records/{rid}/action", headers=hdr, json={"action": "ONBOARD"}).json()["data"]["status"] == "ONBOARD"
    assert client.post(f"{BASE}/work-study/records/{rid}/action", headers=hdr, json={"action": "TERMINATE", "reason": "短"}).json()["code"] != 0
    # 在岗期间录月度考核（累计补贴）——先重建到 ONBOARD 态验证月度
    # 上面已 ONBOARD；录两月：合格 300 + 优 500 → subsidy_total 800
    assert client.post(f"{BASE}/work-study/records/{rid}/monthly", headers=hdr,
                       json={"monthCode": "2025-10", "rating": "PASS", "subsidyAmount": 300, "workHours": 40}).json()["code"] == 0
    # 同月重复 → 冲突
    assert client.post(f"{BASE}/work-study/records/{rid}/monthly", headers=hdr,
                       json={"monthCode": "2025-10", "subsidyAmount": 100}).json()["code"] != 0
    assert client.post(f"{BASE}/work-study/records/{rid}/monthly", headers=hdr,
                       json={"monthCode": "2025-11", "rating": "GOOD", "subsidyAmount": 500}).json()["code"] == 0
    # FAIL 不计补贴
    assert client.post(f"{BASE}/work-study/records/{rid}/monthly", headers=hdr,
                       json={"monthCode": "2025-12", "rating": "FAIL", "subsidyAmount": 999}).json()["data"]["subsidyAmount"] == 0
    mon = client.get(f"{BASE}/work-study/records/{rid}/monthly", headers=hdr).json()["data"]["items"]
    assert len(mon) == 3
    recs = client.get(f"{BASE}/work-study/records", headers=hdr, params={"postId": pid}).json()["data"]["items"]
    assert float(next(x for x in recs if x["recordId"] == rid)["subsidyTotal"]) == 800
    # 终止
    t = client.post(f"{BASE}/work-study/records/{rid}/action", headers=hdr, json={"action": "TERMINATE", "reason": "学期结束岗位撤销"}).json()
    assert t["code"] == 0 and t["data"]["status"] == "TERMINATED"


def test_loan_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    lid = client.post(f"{BASE}/loans", headers=hdr, json={
        "studentId": sid, "loanType": "ORIGIN", "bankName": "农行", "bankLast4": "6222000012346411",
        "yearCode": "2025-2026", "amount": 8000}).json()["data"]["loanId"]
    lst = client.get(f"{BASE}/loans", headers=hdr).json()["data"]["items"]
    row = next(x for x in lst if x["loanId"] == lid)
    assert row["bankLast4"] == "6411" and row["status"] == "REGISTERED"
    # 推进 登记→回执→核对→确认
    for exp in ("RECEIPT", "VERIFIED", "CONFIRMED"):
        assert client.post(f"{BASE}/loans/{lid}/advance", headers=hdr).json()["data"]["status"] == exp
    # 已确认不可再推进
    assert client.post(f"{BASE}/loans/{lid}/advance", headers=hdr).json()["code"] != 0
    # 非法类型
    assert client.post(f"{BASE}/loans", headers=hdr, json={"studentId": sid, "loanType": "XX"}).json()["code"] != 0


def test_fee_reduction_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    # 理由过短
    r0 = client.post(f"{BASE}/fee-reductions", headers=hdr, json={"studentId": sid, "itemType": "TEMP_AID", "reason": "短"})
    assert r0.status_code == 422 or r0.json().get("code") not in (0, None)
    fid = client.post(f"{BASE}/fee-reductions", headers=hdr, json={
        "studentId": sid, "itemType": "TEMP_AID", "amount": 2000, "reason": "家中突发变故申请临时补助"}).json()["data"]["feeId"]
    # 未批准不可发放
    assert client.post(f"{BASE}/fee-reductions/{fid}/issue", headers=hdr).json()["code"] != 0
    # 批准→发放
    assert client.post(f"{BASE}/fee-reductions/{fid}/review", headers=hdr, json={"action": "APPROVE"}).json()["data"]["status"] == "APPROVED"
    iss = client.post(f"{BASE}/fee-reductions/{fid}/issue", headers=hdr).json()
    assert iss["code"] == 0 and iss["data"]["status"] == "ISSUED"
    # 驳回意见过短
    fid2 = client.post(f"{BASE}/fee-reductions", headers=hdr, json={
        "studentId": sid, "itemType": "REDUCTION", "reason": "申请学费减免理由充分"}).json()["data"]["feeId"]
    assert client.post(f"{BASE}/fee-reductions/{fid2}/review", headers=hdr, json={"action": "REJECT", "opinion": "短"}).json()["code"] != 0
    assert client.post(f"{BASE}/fee-reductions/{fid2}/review", headers=hdr, json={"action": "REJECT", "opinion": "不符合减免条件予以驳回"}).json()["data"]["status"] == "REJECTED"
