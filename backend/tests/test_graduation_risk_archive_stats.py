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

def test_risk_list_filter_by_student(client, auth_headers, db_mode):
    """gdStudentId 过滤：只返回该生风险，不串其他学生。"""
    h = auth_headers
    sid_a = _gd_student(client, h, "RKF01", "过滤生甲")
    sid_b = _gd_student(client, h, "RKF02", "过滤生乙")
    client.post(f"{GD_RISK}/scan", headers=h)

    only_a = client.get(GD_RISK, headers=h, params={"gdStudentId": sid_a}).json()["data"]["items"]
    assert len(only_a) >= 1
    assert all(str(r["gdStudentId"]) == str(sid_a) for r in only_a)

    only_b = client.get(GD_RISK, headers=h, params={"gdStudentId": sid_b}).json()["data"]["items"]
    assert all(str(r["gdStudentId"]) == str(sid_b) for r in only_b)
    a_ids = {r["id"] for r in only_a}
    assert a_ids.isdisjoint({r["id"] for r in only_b})


def _seed_topic(title="预警课题", capacity=5):
    """直接落一条已入池题目（题目库无 POST API，与 test_graduation_student 同法）。"""
    from app.db.session import get_sessionmaker
    from app.models import GraduationTopic
    MAIN_TID = 1000000000000000001
    db = get_sessionmaker()()
    try:
        t = GraduationTopic(tenant_id=MAIN_TID, title=title, source="教师申报", source_type="TEACHER",
                            advisor_name="王芳", major_name="软件技术", capacity=capacity, selected=0,
                            review_status="APPROVED", status="CONFIRMED")
        db.add(t)
        db.commit()
        db.refresh(t)
        return str(t.id)
    finally:
        db.close()


def test_risk_scan_r06_insufficient_guidance(client, auth_headers, db_mode):
    """GD-R06 指导记录不足：学生推进到中期但指导记录 < 3 → 扫描生成 R06。"""
    h = auth_headers
    gid = _gd_student(client, h, "R06A", "指导不足生")
    tid = _seed_topic("R06课题")
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    client.post(f"{GD_STU}/{gid}/assign-advisor", headers=h, json={"advisorName": "王芳"})
    assert client.post(f"{GD_STU}/{gid}/stage", headers=h, json={"action": "ADVANCE"}).json()["data"]["stage"] == "GUIDING"
    assert client.post(f"{GD_STU}/{gid}/stage", headers=h, json={"action": "ADVANCE"}).json()["data"]["stage"] == "MIDTERM"

    client.post(f"{GD_RISK}/scan", headers=h)
    items = client.get(GD_RISK, headers=h, params={"riskCode": "GD-R06", "gdStudentId": gid}).json()["data"]["items"]
    assert len(items) >= 1 and items[0]["riskCode"] == "GD-R06"


def test_risk_scan_r12_materials_not_archived(client, auth_headers, db_mode):
    """GD-R12 材料未归档：学生节点已归档但归档记录未 FILED → 扫描生成 R12。"""
    h = auth_headers
    gid = _gd_student(client, h, "R12A", "未归档生")
    assert client.post(f"{GD_STU}/{gid}/stage", headers=h, json={"action": "ARCHIVE"}).json()["data"]["stage"] == "ARCHIVED"

    client.post(f"{GD_RISK}/scan", headers=h)
    items = client.get(GD_RISK, headers=h, params={"riskCode": "GD-R12", "gdStudentId": gid}).json()["data"]["items"]
    assert len(items) >= 1 and items[0]["riskCode"] == "GD-R12"
