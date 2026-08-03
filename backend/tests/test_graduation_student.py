"""毕业设计中心 · 毕设学生测试（MySQL 真库 via db_mode）：建档 + 学生-选题分配闭环
（selected 收口）+ 满员/未确认拒绝 + 退选 + 节点状态机 + 风险 + 统计 + Excel 导入导出。"""
from __future__ import annotations

from conftest import make_org_class

import base64
from uuid import uuid4

from sqlalchemy import select

GD_STU = "/api/v1/graduation/gd-students"
GD_BATCH = "/api/v1/graduation/batches"
GD_TOPIC = "/api/v1/graduation/topics"
STU = "/api/v1/students"


def _student(graduation_client, h, no, name="毕设测试学生"):
    return graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]


def _batch(graduation_client, h, no="GD-STU-B1"):
    return graduation_client.post(GD_BATCH, headers=h, json={
        "batchName": "2026届毕设", "batchNo": no, "gradeYear": "2026届", "plannedCount": 50
    }).json()["data"]["id"]


def _topic(graduation_client, h, title="测试课题A", capacity=2):
  # topics are seeded via graduation API list - we need to create via DB seed or use existing endpoint
  # graduation topics don't have POST in API - seed directly in test via client get after _seed_topic helper
    from app.db.session import get_sessionmaker
    from app.models import GraduationTopic
    MAIN_TID = 1000000000000000001
    bid = getattr(graduation_client, "_active_batch_id", None) or _batch(graduation_client, h, f"GD-STU-TOP-{uuid4().hex[:8]}")
    db = get_sessionmaker()()
    try:
        t = GraduationTopic(tenant_id=MAIN_TID, batch_id=int(bid), title=title, source="教师申报", source_type="TEACHER",
                            advisor_name="王芳", major_name="软件技术", capacity=capacity, selected=0,
                            review_status="APPROVED", status="CONFIRMED")
        db.add(t)
        db.commit()
        db.refresh(t)
        return str(t.id)
    finally:
        db.close()


def _record(graduation_client, h, sid, batch_id=None):
    body = {"studentId": sid}
    if batch_id:
        body["batchId"] = batch_id
    return graduation_client.post(GD_STU, headers=h, json=body).json()["data"]["id"]


def test_create_and_list(graduation_client, auth_headers, db_mode):
    sid = _student(graduation_client, auth_headers, "S-GDS-001")
    bid = _batch(graduation_client, auth_headers, "GD-STU-L1")
    r = graduation_client.post(GD_STU, headers=auth_headers, json={"studentId": sid, "batchId": bid}).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["stage"] == "TOPIC_SELECTING" and d["batchId"] == bid and d["topicId"] == ""
    lst = graduation_client.get(GD_STU, headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] >= 1
    assert graduation_client.post(GD_STU, headers=auth_headers, json={"studentId": sid, "batchId": bid}).json()["code"] != 0


def test_assign_topic_updates_selected(graduation_client, auth_headers, db_mode):
    tid = _topic(graduation_client, auth_headers, "选题分配测试", capacity=2)
    rid = _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-010"))
    a = graduation_client.post(f"{GD_STU}/{rid}/assign-topic", headers=auth_headers, json={"topicId": tid}).json()
    assert a["code"] == 0
    assert a["data"]["topicId"] == tid and a["data"]["stage"] == "TASKBOOK_CONFIRM"
    assert a["data"]["topicTitle"] and a["data"]["advisorName"]
    topics = graduation_client.get(GD_TOPIC, headers=auth_headers).json()["data"]["items"]
    row = [t for t in topics if t["id"] == tid][0]
    assert row["selected"] == 1


def test_assign_full_rejected(graduation_client, auth_headers, db_mode):
    tid = _topic(graduation_client, auth_headers, "满员选题", capacity=1)
    r1 = _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-020"))
    assert graduation_client.post(f"{GD_STU}/{r1}/assign-topic", headers=auth_headers, json={"topicId": tid}).json()["code"] == 0
    r2 = _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-021"))
    assert graduation_client.post(f"{GD_STU}/{r2}/assign-topic", headers=auth_headers, json={"topicId": tid}).json()["code"] != 0


def test_unassign_releases(graduation_client, auth_headers, db_mode):
    tid = _topic(graduation_client, auth_headers, "退选测试", capacity=2)
    rid = _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-030"))
    graduation_client.post(f"{GD_STU}/{rid}/assign-topic", headers=auth_headers, json={"topicId": tid})
    u = graduation_client.post(f"{GD_STU}/{rid}/unassign-topic", headers=auth_headers, json={"reason": "学生申请退选"}).json()
    assert u["code"] == 0 and u["data"]["topicId"] == "" and u["data"]["stage"] == "TOPIC_SELECTING"
    topics = graduation_client.get(GD_TOPIC, headers=auth_headers).json()["data"]["items"]
    assert [t for t in topics if t["id"] == tid][0]["selected"] == 0


def test_stage_machine(graduation_client, auth_headers, db_mode):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import GraduationArchiveRecord, GraduationProposal, GraduationRiskCase, GraduationTaskBook

    tid = _topic(graduation_client, auth_headers, "状态机测试", capacity=2)
    rid = _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-040"))
    assert graduation_client.post(f"{GD_STU}/{rid}/stage", headers=auth_headers, json={"action": "ADVANCE"}).json()["code"] != 0
    graduation_client.post(f"{GD_STU}/{rid}/assign-topic", headers=auth_headers, json={"topicId": tid})
    graduation_client.post(f"{GD_STU}/{rid}/assign-advisor", headers=auth_headers, json={"advisorName": "李老师"})
    db = get_sessionmaker()()
    try:
        db.add(GraduationTaskBook(
            tenant_id=1000000000000000001, gd_student_id=int(rid), status="CONFIRMED",
            objective="目标", content="内容", confirmed_at=datetime.utcnow(), history_json=[],
        ))
        db.add(GraduationProposal(
            tenant_id=1000000000000000001, gd_student_id=int(rid), version="v1",
            status="APPROVED", submit_at=datetime.utcnow(),
        ))
        db.add(GraduationArchiveRecord(
            tenant_id=1000000000000000001, gd_student_id=int(rid), status="FILED",
            missing_items=[], checklist_json=[], manifest_hash="test-manifest",
        ))
        db.commit()
    finally:
        db.close()
    assert graduation_client.post(f"{GD_STU}/{rid}/stage", headers=auth_headers, json={"action": "ADVANCE"}).json()["data"]["stage"] == "GUIDING"
    assert graduation_client.post(f"{GD_STU}/{rid}/stage", headers=auth_headers, json={"action": "ADVANCE"}).json()["data"]["stage"] == "MIDTERM"
    db = get_sessionmaker()()
    try:
        for risk in db.scalars(select(GraduationRiskCase).where(
            GraduationRiskCase.gd_student_id == int(rid),
            GraduationRiskCase.is_deleted.is_(False),
        )).all():
            risk.status = "CLOSED"
        db.commit()
    finally:
        db.close()
    assert graduation_client.post(f"{GD_STU}/{rid}/stage", headers=auth_headers, json={"action": "ARCHIVE"}).json()["data"]["stage"] == "ARCHIVED"
    assert graduation_client.put(f"{GD_STU}/{rid}", headers=auth_headers, json={"advisorName": "x"}).json()["code"] != 0


def test_risk_and_stats(graduation_client, auth_headers, db_mode):
    rid = _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-050"))
    r = graduation_client.post(f"{GD_STU}/{rid}/risk", headers=auth_headers, json={"riskLevel": "HIGH", "reason": "进度滞后"}).json()
    assert r["code"] == 0 and r["data"]["riskLevel"] == "HIGH"
    s = graduation_client.get(f"{GD_STU}/stats", headers=auth_headers).json()
    assert s["code"] == 0 and s["data"]["total"] >= 1 and s["data"]["highRisk"] >= 1


def test_export_xlsx(graduation_client, auth_headers, db_mode):
    _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-060"))
    ex = graduation_client.post(f"{GD_STU}/export", headers=auth_headers).json()
    assert ex["code"] == 0 and ex["data"]["rowCount"] >= 1
    raw = base64.b64decode(ex["data"]["contentBase64"])
    assert raw[:2] == b"PK"


def test_import(graduation_client, auth_headers, db_mode):
    _student(graduation_client, auth_headers, "S-GDS-100", "导入学生甲")
    bid = _batch(graduation_client, auth_headers, "GD-STU-IMP1")
    batch_no = graduation_client.get(f"{GD_BATCH}/{bid}", headers=auth_headers).json()["data"]["batchNo"]
    rows = [{"studentNo": "S-GDS-100", "batchNo": batch_no, "advisorName": "王芳"},
            {"studentNo": ""}, {"studentNo": "S-NOEXIST"}]
    dry = graduation_client.post(f"{GD_STU}/import/dry-run", headers=auth_headers, json={"rows": rows}).json()
    assert dry["code"] == 0 and dry["data"]["invalidRows"] == 2
    ok_rows = [{"studentNo": "S-GDS-100", "batchNo": batch_no, "advisorName": "王芳"}]
    dry2 = graduation_client.post(f"{GD_STU}/import/dry-run", headers=auth_headers, json={"rows": ok_rows}).json()
    assert dry2["data"]["validRows"] == 1
    imp = graduation_client.post(f"{GD_STU}/import/confirm", headers=auth_headers, json={"rows": ok_rows}).json()
    assert imp["code"] == 0 and imp["data"]["created"] == 1


def test_detail(graduation_client, auth_headers, db_mode):
    rid = _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-070"))
    d = graduation_client.get(f"{GD_STU}/{rid}", headers=auth_headers).json()
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


def test_subpanels_eligibility_group_defense_grad_qual(graduation_client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent
    rid = _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-080"))
    e = graduation_client.post(f"{GD_STU}/{rid}/eligibility", headers=auth_headers,
                    json={"status": "QUALIFIED", "reason": "学籍正常"}).json()
    assert e["code"] == 0 and e["data"]["eligibilityStatus"] == "QUALIFIED"
    g = graduation_client.post(f"{GD_STU}/{rid}/group", headers=auth_headers,
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
    d = graduation_client.post(f"{GD_STU}/{rid}/defense-group", headers=auth_headers,
                    json={"defenseGroupId": gid, "reason": "安排答辩"}).json()
    assert d["code"] == 0 and d["data"]["defenseGroupId"] == gid
    q = graduation_client.post(f"{GD_STU}/{rid}/grad-qual", headers=auth_headers,
                    json={"status": "PASS", "note": "教务预审通过", "reason": "联动"}).json()
    assert q["code"] != 0 and "不再直接裁决" in q["message"]
    graduation_client._active_batch_id = str(bid)
    lst = graduation_client.get(f"{GD_STU}", headers=auth_headers, params={"eligibility": "QUALIFIED"}).json()
    assert lst["code"] == 0 and any(x["id"] == rid for x in lst["data"]["items"])
    groups = graduation_client.get(f"{GD_STU}/groups", headers=auth_headers).json()
    assert groups["code"] == 0 and "第1组" in groups["data"]


def test_batch_group_and_archive(graduation_client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationArchiveRecord

    r1 = _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-081"))
    r2 = _record(graduation_client, auth_headers, _student(graduation_client, auth_headers, "S-GDS-082"))
    bg = graduation_client.post(f"{GD_STU}/batch-group", headers=auth_headers,
                     json={"recordIds": [r1, r2], "groupName": "批量组A", "reason": "批量"}).json()
    assert bg["code"] == 0 and bg["data"]["updated"] == 2
    db = get_sessionmaker()()
    try:
        db.add(GraduationArchiveRecord(
            tenant_id=1000000000000000001, gd_student_id=int(r1), status="FILED",
            missing_items=[], checklist_json=[], manifest_hash="test-manifest",
        ))
        db.commit()
    finally:
        db.close()
    ba = graduation_client.post(f"{GD_STU}/batch-archive", headers=auth_headers,
                     json={"recordIds": [r1], "reason": "结业归档"}).json()
    assert ba["code"] == 0 and ba["data"]["archived"] == 1
    archived = graduation_client.get(f"{GD_STU}", headers=auth_headers, params={"archiveView": "archived"}).json()
    assert any(x["id"] == r1 for x in archived["data"]["items"])
