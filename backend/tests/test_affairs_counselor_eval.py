"""13A-D 辅导员考评端到端（真实 DB）。

覆盖：建指标→录评分(总分=各项之和,同周期同人唯一 upsert)→发布(发布后不可改)→
辅导员申诉→复核(维持/调整可改分)；同名指标/空周期/已发布改/无申诉复核等校验。
"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_counselor_eval_full_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    # 建指标
    i1 = client.post(f"{BASE}/counselor-eval/indicators", headers=hdr,
                     json={"name": "师德师风", "weight": 30, "maxScore": 100}).json()
    assert i1["code"] == 0
    ind_id = i1["data"]["indicatorId"]
    # 同名冲突
    assert client.post(f"{BASE}/counselor-eval/indicators", headers=hdr, json={"name": "师德师风"}).json()["code"] != 0
    client.post(f"{BASE}/counselor-eval/indicators", headers=hdr, json={"name": "学生工作", "weight": 40})
    assert len(client.get(f"{BASE}/counselor-eval/indicators", headers=hdr).json()["data"]["items"]) >= 2
    # 录评分（总分=90+85=175）
    e = client.post(f"{BASE}/counselor-eval/evals", headers=hdr, json={
        "periodCode": "2025-2026-1", "counselorKey": "teacher01", "counselorName": "李辅导员",
        "scores": {ind_id: 90, "x": 85}}).json()
    assert e["code"] == 0 and float(e["data"]["totalScore"]) == 175
    eid = e["data"]["evalId"]
    # upsert 覆盖（同周期同人唯一）
    e2 = client.post(f"{BASE}/counselor-eval/evals", headers=hdr, json={
        "periodCode": "2025-2026-1", "counselorKey": "teacher01", "scores": {ind_id: 95}}).json()
    assert e2["data"]["evalId"] == eid and float(e2["data"]["totalScore"]) == 95
    # 发布
    p = post_versioned(client, f"{BASE}/counselor-eval/evals/{eid}/publish", headers=hdr).json()
    assert p["code"] == 0 and p["data"]["status"] == "PUBLISHED"
    # 发布后不可改
    assert client.post(f"{BASE}/counselor-eval/evals", headers=hdr, json={
        "periodCode": "2025-2026-1", "counselorKey": "teacher01", "scores": {ind_id: 100}}).json()["code"] != 0
    # 申诉
    a = post_versioned(client, f"{BASE}/counselor-eval/evals/{eid}/appeal", headers=hdr,
                    json={"reason": "对师德指标评分有异议申请复核"}).json()
    assert a["code"] == 0 and a["data"]["appealStatus"] == "SUBMITTED"
    # 复核调整分数
    r = post_versioned(client, f"{BASE}/counselor-eval/evals/{eid}/appeal-review", headers=hdr, json={
        "result": "ADJUSTED", "opinion": "经复核上调师德得分", "scores": {ind_id: 98}}).json()
    assert r["code"] == 0 and r["data"]["appealStatus"] == "REVIEWED" and float(r["data"]["totalScore"]) == 98
    # 无待复核申诉再复核 → 冲突
    assert post_versioned(client, f"{BASE}/counselor-eval/evals/{eid}/appeal-review", headers=hdr,
                       json={"result": "UPHELD", "opinion": "重复复核测试意见"}).json()["code"] != 0


def test_eval_validation(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    # 空名指标
    r = client.post(f"{BASE}/counselor-eval/indicators", headers=hdr, json={"name": ""})
    assert r.status_code == 422 or r.json().get("code") not in (0, None)
    # 空周期录分
    r2 = client.post(f"{BASE}/counselor-eval/evals", headers=hdr, json={"periodCode": "", "counselorKey": "t"})
    assert r2.status_code == 422 or r2.json().get("code") not in (0, None)
