"""毕业设计中心 · 毕设看板测试：真实聚合结构 + 待办含 hint/route + 答辩待发布计数联动 + 风险预警为列表。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

DASH = "/api/v1/graduation/dashboard"
DG = "/api/v1/graduation/defense-groups"
GD_BATCH = "/api/v1/graduation/batches"


def _todo(data, tid):
    return next((t for t in data["todos"] if t["id"] == tid), None)


def test_dashboard_structure_and_todo_hints(client, auth_headers, db_mode):
    h = auth_headers
    data = client.get(DASH, headers=h).json()["data"]
    assert isinstance(data["stats"], list) and len(data["stats"]) >= 5
    assert isinstance(data["flow"], list) and data["flow"]
    assert isinstance(data["riskAlerts"], list)
    # 待办每项都有 hint + route（前端模板依赖 t.hint）
    assert data["todos"]
    for t in data["todos"]:
        assert t["hint"] and t["route"]
    assert _todo(data, "t4")["label"].startswith("答辩组")


def test_pending_defense_count_reflects_new_group(client, auth_headers, db_mode):
    h = auth_headers
    before = _todo(client.get(DASH, headers=h).json()["data"], "t4")["count"]

    client.post(DG, headers=h, json={"groupName": "看板答辩组", "chair": "组长", "location": "L1",
                                     "members": ["评委1"], "secretary": "秘书"})

    after = _todo(client.get(DASH, headers=h).json()["data"], "t4")["count"]
    assert after == before + 1

    stat = next(s for s in client.get(DASH, headers=h).json()["data"]["stats"] if s["label"] == "答辩待发布")
    assert int(stat["value"]) == after


def test_dashboard_batch_info_reflects_running_batch(client, auth_headers, db_mode):
    """看板批次信息回真：进行中批次的名称/起止/状态如实反映，而非硬编码。"""
    h = auth_headers
    bid = client.post(GD_BATCH, headers=h, json={
        "batchName": "看板回真专用批次2027", "batchNo": "DASH-RUN-1", "gradeYear": "2027届",
        "startDate": "2026-09-01", "endDate": "2027-06-30", "plannedCount": 30
    }).json()["data"]["id"]
    client.post(f"{GD_BATCH}/{bid}/activate", headers=h)

    data = client.get(DASH, headers=h).json()["data"]
    assert data["batchName"] == "看板回真专用批次2027"
    assert data["batchStatus"] == "进行中"
    assert "2026-09-01" in data["batchRange"] and "2027-06-30" in data["batchRange"]
