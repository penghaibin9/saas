"""13A 增强(b) · 辅导员考评加权总分（真实 MySQL）。

weighted_total_score = Σ(score×weight)/Σweight（按指标权重加权平均，附加列）；
total_score 保持各项直和（历史口径不变）。无可加权项→weightedTotalScore=None。
"""
from __future__ import annotations

BASE = "/api/v1/student-affairs"


def _hdr(client, login):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_eval_weighted_total(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    a = client.post(f"{BASE}/counselor-eval/indicators", headers=hdr,
                    json={"name": "师德师风W", "weight": 30, "maxScore": 100}).json()["data"]["indicatorId"]
    b = client.post(f"{BASE}/counselor-eval/indicators", headers=hdr,
                    json={"name": "学生工作W", "weight": 70, "maxScore": 100}).json()["data"]["indicatorId"]
    e = client.post(f"{BASE}/counselor-eval/evals", headers=hdr, json={
        "periodCode": "2025-2026-W", "counselorKey": "tW01", "counselorName": "李W",
        "scores": {a: 90, b: 80}}).json()["data"]
    # 直和口径不变
    assert float(e["totalScore"]) == 170
    # 加权平均 = (90*30 + 80*70)/100 = 83
    assert float(e["weightedTotalScore"]) == 83.0, e


def test_eval_weighted_none_when_no_weighted_indicator(client, db_mode):
    """scores 全用非指标 key（无权重可匹配）→ weightedTotalScore 为 None，前端回退原始总分。"""
    hdr = _hdr(client, "school_admin01")
    e = client.post(f"{BASE}/counselor-eval/evals", headers=hdr, json={
        "periodCode": "2025-2026-WX", "counselorKey": "tWX", "scores": {"free1": 50, "free2": 40}}).json()["data"]
    assert float(e["totalScore"]) == 90
    assert e["weightedTotalScore"] is None, e


def test_eval_weighted_recomputed_on_adjust(client, db_mode):
    """申诉复核 ADJUSTED 改分后加权总分同步重算。"""
    hdr = _hdr(client, "school_admin01")
    a = client.post(f"{BASE}/counselor-eval/indicators", headers=hdr,
                    json={"name": "复核指标W", "weight": 50}).json()["data"]["indicatorId"]
    e = client.post(f"{BASE}/counselor-eval/evals", headers=hdr, json={
        "periodCode": "2025-2026-ADJ", "counselorKey": "tADJ", "scores": {a: 60}}).json()["data"]
    eid = e["evalId"]
    assert float(e["weightedTotalScore"]) == 60.0
    client.post(f"{BASE}/counselor-eval/evals/{eid}/publish", headers=hdr)
    client.post(f"{BASE}/counselor-eval/evals/{eid}/appeal", headers=hdr,
                json={"reason": "对复核指标评分有异议申请复核"})
    r = client.post(f"{BASE}/counselor-eval/evals/{eid}/appeal-review", headers=hdr, json={
        "result": "ADJUSTED", "opinion": "经复核上调得分", "scores": {a: 95}}).json()["data"]
    assert float(r["weightedTotalScore"]) == 95.0, r
