"""毕业设计中心 · 毕设看板测试：真实聚合结构 + 待办含 hint/route + 答辩待发布计数联动 + 风险预警为列表。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

DASH = "/api/v1/graduation/dashboard"
DG = "/api/v1/graduation/defense-groups"


def _todo(data, tid):
    return next((t for t in data["todos"] if t["id"] == tid), None)


def test_dashboard_structure_and_todo_hints(graduation_client, auth_headers, db_mode):
    h = auth_headers
    data = graduation_client.get(DASH, headers=h).json()["data"]
    assert isinstance(data["stats"], list) and len(data["stats"]) >= 5
    assert isinstance(data["flow"], list) and data["flow"]
    assert isinstance(data["riskAlerts"], list)
    # 待办每项都有 hint + route（前端模板依赖 t.hint）
    assert data["todos"]
    for t in data["todos"]:
        assert t["hint"] and t["route"]
    assert _todo(data, "t4")["label"].startswith("答辩组")


def test_pending_defense_count_reflects_new_group(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bid = graduation_client.post("/api/v1/graduation/batches", headers=h, json={
        "batchName": "看板答辩批", "batchNo": "GD-DASH-DF", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]
    before = _todo(graduation_client.get(DASH, headers=h, params={"batchId": bid}).json()["data"], "t4")["count"]

    graduation_client.post(DG, headers=h, params={"batchId": bid}, json={"groupName": "看板答辩组", "batchId": bid, "chair": "组长", "location": "L1",
                                     "members": ["评委1"], "secretary": "秘书"})

    after = _todo(graduation_client.get(DASH, headers=h, params={"batchId": bid}).json()["data"], "t4")["count"]
    assert after == before + 1

    stat = next(s for s in graduation_client.get(DASH, headers=h, params={"batchId": bid}).json()["data"]["stats"]
                if s["label"] == "答辩待发布")
    assert int(stat["value"]) == after

    audit = graduation_client.get("/api/v1/graduation/audit-logs", headers=h).json()["data"]["items"][0]
    assert audit["requestId"].startswith("req-")
    assert audit["requestPath"] == DG
    assert audit["clientIp"]
