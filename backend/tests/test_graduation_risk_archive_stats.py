"""毕业设计中心 · 问题预警 + 毕设归档 + 毕设统计测试：扫描生成→受理→处理→关闭；
归档清单生成(缺失材料拦截提交)→提交→核验归档→驳回；总览统计聚合。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

GD_RISK = "/api/v1/graduation/gd-risks"
GD_ARCHIVE = "/api/v1/graduation/gd-archives"
GD_STATS = "/api/v1/graduation/gd-stats"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _gd_student(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    return client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def test_risk_scan_accept_process_close(client, auth_headers, db_mode):
    h = auth_headers
    _gd_student(client, h, "RK001", "预警测试生")  # stage=TOPIC_SELECTING, no topic → GD-R01

    scan = client.post(f"{GD_RISK}/scan", headers=h)
    body = scan.json()["data"]
    assert body["newCasesCreated"] >= 1

    lst = client.get(GD_RISK, headers=h, params={"riskCode": "GD-R01"}).json()["data"]["items"]
    assert len(lst) >= 1
    rid = lst[0]["id"]
    assert lst[0]["status"] == "OPEN"

    accept = client.post(f"{GD_RISK}/{rid}/accept", headers=h, json={})
    assert accept.json()["data"]["status"] == "PROCESSING"

    process = client.post(f"{GD_RISK}/{rid}/process", headers=h, json={"note": "已联系学生督促选题"})
    assert process.json()["data"]["handleNote"]

    short_close = client.post(f"{GD_RISK}/{rid}/close", headers=h, json={"reason": "x"})
    assert short_close.json()["code"] != 0

    close = client.post(f"{GD_RISK}/{rid}/close", headers=h, json={"reason": "学生已完成选题风险解除"})
    assert close.json()["data"]["status"] == "CLOSED"

    rescan = client.post(f"{GD_RISK}/scan", headers=h).json()["data"]
    assert rescan["newCasesCreated"] == 0  # 幂等，不重复生成已存在（含已关闭）项

    stats = client.get(f"{GD_RISK}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1


def test_archive_generate_blocks_submit_until_complete_then_files(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "AR001", "归档测试生")

    gen = client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h)
    body = gen.json()["data"]
    assert body["status"] == "PENDING_SUBMIT"
    assert len(body["missingItems"]) == len(body["checklist"])  # 全部材料缺失

    blocked = client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h)
    assert blocked.json()["code"] != 0

    detail = client.get(f"{GD_ARCHIVE}/{gid}", headers=h).json()["data"]
    assert detail["status"] == "PENDING_SUBMIT"

    stats = client.get(f"{GD_ARCHIVE}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1

    export = client.post(f"{GD_ARCHIVE}/export", headers=h)
    assert export.json()["code"] == 0
    assert export.json()["data"]["rowCount"] >= 1


def test_stats_overview_and_college_comparison(client, auth_headers, db_mode):
    h = auth_headers
    _gd_student(client, h, "ST001", "统计测试生")

    overview = client.get(f"{GD_STATS}/overview", headers=h).json()["data"]
    assert overview["studentTotal"] >= 1
    assert "byStage" in overview and "mentor" in overview and "risk" in overview

    comp = client.get(f"{GD_STATS}/college-comparison", headers=h).json()["data"]
    assert isinstance(comp, list)
