"""毕业设计 P0：学生列表与导出筛选一致；按 batchId/材料/答辩组/资格/风险导出。"""
from __future__ import annotations

GD_STU = "/api/v1/graduation/gd-students"
GD_BATCH = "/api/v1/graduation/batches"
STU = "/api/v1/students"


def _student(client, h, no, name="导出一致学生"):
    return client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]


def _batch(client, h, no):
    return client.post(GD_BATCH, headers=h, json={
        "batchName": f"批次{no}", "batchNo": no, "gradeYear": "2026届", "plannedCount": 50
    }).json()["data"]["id"]


def _record(client, h, sid, batch_id=None, **extra):
    body = {"studentId": sid}
    if batch_id:
        body["batchId"] = batch_id
    body.update(extra)
    return client.post(GD_STU, headers=h, json=body).json()["data"]["id"]


def _list_total(client, h, **params):
    r = client.get(GD_STU, headers=h, params=params).json()
    assert r["code"] == 0
    return r["data"]["total"]


def _export_count(client, h, **params):
    r = client.post(f"{GD_STU}/export", headers=h, params=params).json()
    assert r["code"] == 0
    return r["data"]["rowCount"]


def test_export_filters_match_list_total(client, auth_headers, db_mode):
    """列表 total 与导出 rowCount 在相同筛选下必须一致。"""
    b1 = _batch(client, auth_headers, "GD-P0-EXP-B1")
    b2 = _batch(client, auth_headers, "GD-P0-EXP-B2")
    s1 = _student(client, auth_headers, "S-P0-E01", "甲同学")
    s2 = _student(client, auth_headers, "S-P0-E02", "乙同学")
    s3 = _student(client, auth_headers, "S-P0-E03", "丙同学")
    r1 = _record(client, auth_headers, s1, b1)
    _record(client, auth_headers, s2, b1)
    _record(client, auth_headers, s3, b2)

    # 按 batchId
    t = _list_total(client, auth_headers, batchId=b1)
    assert _export_count(client, auth_headers, batchId=b1) == t
    assert t >= 2

    # 按风险：先打标 HIGH
    assert client.post(f"{GD_STU}/{r1}/risk", headers=auth_headers,
                       json={"riskLevel": "HIGH", "reason": "定向测试风险标记"}).json()["code"] == 0
    t_risk = _list_total(client, auth_headers, batchId=b1, riskLevel="HIGH")
    assert _export_count(client, auth_headers, batchId=b1, riskLevel="HIGH") == t_risk
    assert t_risk >= 1

    # 按未分答辩组
    t_def = _list_total(client, auth_headers, batchId=b1, hasDefenseGroup=False)
    assert _export_count(client, auth_headers, batchId=b1, hasDefenseGroup=False) == t_def

    # 按资格
    assert client.post(f"{GD_STU}/{r1}/eligibility", headers=auth_headers,
                       json={"status": "QUALIFIED", "reason": "定向测试资格认定"}).json()["code"] == 0
    t_elig = _list_total(client, auth_headers, batchId=b1, eligibility="QUALIFIED")
    assert _export_count(client, auth_headers, batchId=b1, eligibility="QUALIFIED") == t_elig

    # 按毕业资格
    assert client.post(f"{GD_STU}/{r1}/grad-qual", headers=auth_headers,
                       json={"status": "PASS", "note": "测试", "reason": "定向测试毕业资格"}).json()["code"] == 0
    t_gq = _list_total(client, auth_headers, batchId=b1, gradQualStatus="PASS")
    assert _export_count(client, auth_headers, batchId=b1, gradQualStatus="PASS") == t_gq

    # 材料不完整（多数新建学生材料未齐）
    t_mat = _list_total(client, auth_headers, batchId=b1, materialComplete=False)
    assert _export_count(client, auth_headers, batchId=b1, materialComplete=False) == t_mat


def test_proposal_final_batch_filter(client, auth_headers, db_mode):
    """开题/成果列表支持 batchId，不混查其他批次。"""
    b1 = _batch(client, auth_headers, "GD-P0-PF-B1")
    b2 = _batch(client, auth_headers, "GD-P0-PF-B2")
    _record(client, auth_headers, _student(client, auth_headers, "S-P0-PF1"), b1)
    _record(client, auth_headers, _student(client, auth_headers, "S-P0-PF2"), b2)

    p1 = client.get("/api/v1/graduation/proposals", headers=auth_headers, params={"batchId": b1}).json()
    p2 = client.get("/api/v1/graduation/proposals", headers=auth_headers, params={"batchId": b2}).json()
    assert p1["code"] == 0 and p2["code"] == 0

    f1 = client.get("/api/v1/graduation/finals", headers=auth_headers, params={"batchId": b1}).json()
    assert f1["code"] == 0

    dash = client.get("/api/v1/graduation/dashboard", headers=auth_headers, params={"batchId": b1}).json()
    assert dash["code"] == 0
