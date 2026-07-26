"""毕业设计中心 · 毕设学生测试（MySQL 真库 via db_mode）：建档 + 学生-选题分配闭环
（selected 收口）+ 满员/未确认拒绝 + 退选 + 节点状态机 + 风险 + 统计 + Excel 导入导出。"""
from __future__ import annotations

from conftest import make_org_class

import base64

GD_STU = "/api/v1/graduation/gd-students"
GD_BATCH = "/api/v1/graduation/batches"
GD_TOPIC = "/api/v1/graduation/topics"
STU = "/api/v1/students"


def _student(client, h, no, name="毕设测试学生"):
    return client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]


def _batch(client, h, no="GD-STU-B1"):
    return client.post(GD_BATCH, headers=h, json={
        "batchName": "2026届毕设", "batchNo": no, "gradeYear": "2026届", "plannedCount": 50
    }).json()["data"]["id"]


def _topic(client, h, title="测试课题A", capacity=2):
  # topics are seeded via graduation API list - we need to create via DB seed or use existing endpoint
  # graduation topics don't have POST in API - seed directly in test via client get after _seed_topic helper
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


def _record(client, h, sid, batch_id=None):
    body = {"studentId": sid}
    if batch_id:
        body["batchId"] = batch_id
    return client.post(GD_STU, headers=h, json=body).json()["data"]["id"]


def test_create_and_list(client, auth_headers, db_mode):
    sid = _student(client, auth_headers, "S-GDS-001")
    bid = _batch(client, auth_headers, "GD-STU-L1")
    r = client.post(GD_STU, headers=auth_headers, json={"studentId": sid, "batchId": bid}).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["stage"] == "TOPIC_SELECTING" and d["batchId"] == bid and d["topicId"] == ""
    lst = client.get(GD_STU, headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] >= 1
    assert client.post(GD_STU, headers=auth_headers, json={"studentId": sid, "batchId": bid}).json()["code"] != 0


def test_assign_topic_updates_selected(client, auth_headers, db_mode):
    tid = _topic(client, auth_headers, "选题分配测试", capacity=2)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-GDS-010"))
    a = client.post(f"{GD_STU}/{rid}/assign-topic", headers=auth_headers, json={"topicId": tid}).json()
    assert a["code"] == 0
    assert a["data"]["topicId"] == tid and a["data"]["stage"] == "TASKBOOK_CONFIRM"
    assert a["data"]["topicTitle"] and a["data"]["advisorName"]
    topics = client.get(GD_TOPIC, headers=auth_headers).json()["data"]["items"]
    row = [t for t in topics if t["id"] == tid][0]
    assert row["selected"] == 1


def test_assign_full_rejected(client, auth_headers, db_mode):
    tid = _topic(client, auth_headers, "满员选题", capacity=1)
    r1 = _record(client, auth_headers, _student(client, auth_headers, "S-GDS-020"))
    assert client.post(f"{GD_STU}/{r1}/assign-topic", headers=auth_headers, json={"topicId": tid}).json()["code"] == 0
    r2 = _record(client, auth_headers, _student(client, auth_headers, "S-GDS-021"))
    assert client.post(f"{GD_STU}/{r2}/assign-topic", headers=auth_headers, json={"topicId": tid}).json()["code"] != 0


def test_unassign_releases(client, auth_headers, db_mode):
    tid = _topic(client, auth_headers, "退选测试", capacity=2)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-GDS-030"))
    client.post(f"{GD_STU}/{rid}/assign-topic", headers=auth_headers, json={"topicId": tid})
    u = client.post(f"{GD_STU}/{rid}/unassign-topic", headers=auth_headers, json={"reason": "学生申请退选"}).json()
    assert u["code"] == 0 and u["data"]["topicId"] == "" and u["data"]["stage"] == "TOPIC_SELECTING"
    topics = client.get(GD_TOPIC, headers=auth_headers).json()["data"]["items"]
    assert [t for t in topics if t["id"] == tid][0]["selected"] == 0


def test_stage_machine(client, auth_headers, db_mode):
    tid = _topic(client, auth_headers, "状态机测试", capacity=2)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-GDS-040"))
    assert client.post(f"{GD_STU}/{rid}/stage", headers=auth_headers, json={"action": "ADVANCE"}).json()["code"] != 0
    client.post(f"{GD_STU}/{rid}/assign-topic", headers=auth_headers, json={"topicId": tid})
    client.post(f"{GD_STU}/{rid}/assign-advisor", headers=auth_headers, json={"advisorName": "李老师"})
    assert client.post(f"{GD_STU}/{rid}/stage", headers=auth_headers, json={"action": "ADVANCE"}).json()["data"]["stage"] == "GUIDING"
    assert client.post(f"{GD_STU}/{rid}/stage", headers=auth_headers, json={"action": "ADVANCE"}).json()["data"]["stage"] == "MIDTERM"
    assert client.post(f"{GD_STU}/{rid}/stage", headers=auth_headers, json={"action": "ARCHIVE"}).json()["data"]["stage"] == "ARCHIVED"
    assert client.put(f"{GD_STU}/{rid}", headers=auth_headers, json={"advisorName": "x"}).json()["code"] != 0


def test_risk_and_stats(client, auth_headers, db_mode):
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-GDS-050"))
    r = client.post(f"{GD_STU}/{rid}/risk", headers=auth_headers, json={"riskLevel": "HIGH", "reason": "进度滞后"}).json()
    assert r["code"] == 0 and r["data"]["riskLevel"] == "HIGH"
    s = client.get(f"{GD_STU}/stats", headers=auth_headers).json()
    assert s["code"] == 0 and s["data"]["total"] >= 1 and s["data"]["highRisk"] >= 1


def test_export_xlsx(client, auth_headers, db_mode):
    _record(client, auth_headers, _student(client, auth_headers, "S-GDS-060"))
    ex = client.post(f"{GD_STU}/export", headers=auth_headers).json()
    assert ex["code"] == 0 and ex["data"]["rowCount"] >= 1
    raw = base64.b64decode(ex["data"]["contentBase64"])
    assert raw[:2] == b"PK"


def test_import(client, auth_headers, db_mode):
    _student(client, auth_headers, "S-GDS-100", "导入学生甲")
    bid = _batch(client, auth_headers, "GD-STU-IMP1")
    batch_no = client.get(f"{GD_BATCH}/{bid}", headers=auth_headers).json()["data"]["batchNo"]
    rows = [{"studentNo": "S-GDS-100", "batchNo": batch_no, "advisorName": "王芳"},
            {"studentNo": ""}, {"studentNo": "S-NOEXIST"}]
    dry = client.post(f"{GD_STU}/import/dry-run", headers=auth_headers, json={"rows": rows}).json()
    assert dry["code"] == 0 and dry["data"]["invalidRows"] == 2
    ok_rows = [{"studentNo": "S-GDS-100", "batchNo": batch_no, "advisorName": "王芳"}]
    dry2 = client.post(f"{GD_STU}/import/dry-run", headers=auth_headers, json={"rows": ok_rows}).json()
    assert dry2["data"]["validRows"] == 1
    imp = client.post(f"{GD_STU}/import/confirm", headers=auth_headers, json={"rows": ok_rows}).json()
    assert imp["code"] == 0 and imp["data"]["created"] == 1


def test_detail(client, auth_headers, db_mode):
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-GDS-070"))
    d = client.get(f"{GD_STU}/{rid}", headers=auth_headers).json()
    assert d["code"] == 0 and d["data"]["name"] and "stateFlow" in d["data"] and "auditTrail" in d["data"]


def _defense_group(db_mode, name="测试答辩组", batch_id=None):
    from app.db.session import get_sessionmaker
    from app.models import GraduationBatch, GraduationDefenseGroup
    MAIN_TID = 1000000000000000001
    db = get_sessionmaker()()
    try:
        bid = batch_id
        if not bid:
            b = GraduationBatch(tenant_id=MAIN_TID, batch_name="学生子面板批", batch_no="GD-SUB-1",
                                grade_year="2026届", planned_count=10, status="ACTIVE")
            db.add(b)
            db.flush()
            bid = b.id
        g = GraduationDefenseGroup(tenant_id=MAIN_TID, batch_id=bid, group_name=name,
                                   defense_date="2026-06-01",
                                   location="教学楼A101", student_count=0, published=False)
        db.add(g)
        db.commit()
        db.refresh(g)
        return str(g.id), str(bid)
    finally:
        db.close()


def test_subpanels_eligibility_group_defense_grad_qual(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-GDS-080"))
    e = client.post(f"{GD_STU}/{rid}/eligibility", headers=auth_headers,
                    json={"status": "QUALIFIED", "reason": "学籍正常"}).json()
    assert e["code"] == 0 and e["data"]["eligibilityStatus"] == "QUALIFIED"
    g = client.post(f"{GD_STU}/{rid}/group", headers=auth_headers,
                    json={"groupName": "第1组", "reason": "过程分组"}).json()
    assert g["code"] == 0 and g["data"]["studentGroup"] == "第1组"
    gid, bid = _defense_group(db_mode)
    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(rid))
        stu.batch_id = int(bid)
        stu.stage = "FINAL_CHECK"
        db.commit()
    finally:
        db.close()
    d = client.post(f"{GD_STU}/{rid}/defense-group", headers=auth_headers,
                    json={"defenseGroupId": gid, "reason": "安排答辩"}).json()
    assert d["code"] == 0 and d["data"]["defenseGroupId"] == gid
    q = client.post(f"{GD_STU}/{rid}/grad-qual", headers=auth_headers,
                    json={"status": "PASS", "note": "教务预审通过", "reason": "联动"}).json()
    assert q["code"] == 0 and q["data"]["gradQualStatus"] == "PASS"
    lst = client.get(f"{GD_STU}", headers=auth_headers, params={"eligibility": "QUALIFIED"}).json()
    assert lst["code"] == 0 and any(x["id"] == rid for x in lst["data"]["items"])
    groups = client.get(f"{GD_STU}/groups", headers=auth_headers).json()
    assert groups["code"] == 0 and "第1组" in groups["data"]


def test_batch_group_and_archive(client, auth_headers, db_mode):
    r1 = _record(client, auth_headers, _student(client, auth_headers, "S-GDS-081"))
    r2 = _record(client, auth_headers, _student(client, auth_headers, "S-GDS-082"))
    bg = client.post(f"{GD_STU}/batch-group", headers=auth_headers,
                     json={"recordIds": [r1, r2], "groupName": "批量组A", "reason": "批量"}).json()
    assert bg["code"] == 0 and bg["data"]["updated"] == 2
    ba = client.post(f"{GD_STU}/batch-archive", headers=auth_headers,
                     json={"recordIds": [r1], "reason": "结业归档"}).json()
    assert ba["code"] == 0 and ba["data"]["archived"] == 1
    archived = client.get(f"{GD_STU}", headers=auth_headers, params={"archiveView": "archived"}).json()
    assert any(x["id"] == r1 for x in archived["data"]["items"])
