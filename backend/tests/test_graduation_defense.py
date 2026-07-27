"""毕业设计中心 · 答辩安排闭环测试：
答辩组新建（同名拒绝）→ 可分配学生 → 分配（评委回避导师自动检测）→ 冲突拦截发布 →
编辑解除冲突 → 完整后发布（须组长/地点/学生齐全）→ Excel 导出 → 学生端查看（发布后可见时间地点）。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

from sqlalchemy import select

GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"
DG = "/api/v1/graduation/defense-groups"
BATCH = "/api/v1/graduation/batches"
MOBILE = "/api/v1/mobile"
MAIN = 1000000000000000001


def _stu_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _batch(client, h, no="GD-DF-LOOP"):
    return client.post(BATCH, headers=h, json={
        "batchName": f"答辩闭环批-{no}", "batchNo": no, "gradeYear": "2026届", "plannedCount": 20,
    }).json()["data"]["id"]


def _mentor_id(name):
    from hashlib import sha1
    from app.db.session import get_sessionmaker
    from app.models import GraduationMentor

    teacher_no = f"TEST-{sha1(name.encode('utf-8')).hexdigest()[:12]}"
    db = get_sessionmaker()()
    try:
        mentor = db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == MAIN,
            GraduationMentor.teacher_no == teacher_no,
            GraduationMentor.is_deleted.is_(False),
        ).limit(1)).first()
        if mentor is None:
            mentor = GraduationMentor(
                tenant_id=MAIN, teacher_no=teacher_no, teacher_name=name,
                qualification_status="QUALIFIED",
            )
            db.add(mentor)
            db.flush()
            db.commit()
        return int(mentor.id)
    finally:
        db.close()


def _items(data):
    return data.get("items", []) if isinstance(data, dict) else data


def _force_final_check(name):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import GraduationFinal, GraduationStudent
    db = get_sessionmaker()()
    try:
        for s in db.scalars(select(GraduationStudent).where(GraduationStudent.name == name)).all():
            s.stage = "FINAL_CHECK"
            db.add(GraduationFinal(
                tenant_id=MAIN, gd_student_id=s.id, final_type="定稿", version="v-test",
                submit_at=datetime.utcnow(), status="APPROVED", attachments_json=["test-final-file"],
                plagiarism_rate="10.0%", plagiarism_status="已检测",
            ))
        db.commit()
    finally:
        db.close()


def _student_with_advisor(client, h, no, name, advisor, bid):
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent, GraduationTopic

    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid}).json()["data"]["id"]
    tid = client.post(GD_TOPIC, headers=h, json={
        "title": f"{name}的毕设题目", "sourceType": "TEACHER", "advisorName": advisor,
        "capacity": 1, "submitReview": True, "batchId": bid}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    mentor_id = _mentor_id(advisor)
    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(gid))
        topic = db.get(GraduationTopic, int(tid))
        if stu:
            stu.mentor_id = mentor_id
            stu.advisor_name = advisor
        if topic:
            topic.advisor_mentor_id = mentor_id
            topic.advisor_name = advisor
        db.commit()
    finally:
        db.close()
    return gid


def test_create_and_duplicate(client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(client, h, "GD-DF-DUP")
    ok = client.post(DG, headers=h, params={"batchId": bid}, json={"groupName": "答辩组甲", "batchId": bid, "chair": "组长A",
                                          "location": "A301", "members": ["评委1", "评委2"], "secretary": "秘书A"})
    assert ok.json()["code"] == 0
    assert ok.json()["data"]["groupName"] == "答辩组甲"
    assert ok.json()["data"]["batchId"] == str(bid)

    dup = client.post(DG, headers=h, params={"batchId": bid}, json={"groupName": "答辩组甲", "batchId": bid})
    assert dup.json()["code"] != 0


def test_assign_conflict_then_resolve_and_publish(client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(client, h, "GD-DF-CF")
    chair_id = _mentor_id("组长B")
    secretary_id = _mentor_id("秘书B")
    advisor_id = _mentor_id("张导师")
    judge_x_id = _mentor_id("评委X")
    judge_y_id = _mentor_id("评委Y")
    grp = client.post(DG, headers=h, params={"batchId": bid}, json={"groupName": "答辩组乙", "batchId": bid, "chair": "张导师",
                                           "defenseDate": "2026-06-20 09:00", "location": "B201",
                                           "chairMentorId": advisor_id, "memberMentorIds": [judge_x_id],
                                           "secretary": "秘书B", "secretaryMentorId": secretary_id}).json()["data"]
    gid = grp["id"]
    _student_with_advisor(client, h, "DF001", "答辩甲", "张导师", bid)
    _force_final_check("答辩甲")

    elig = _items(client.get(f"{DG}/eligible-students", headers=h, params={"gid": gid}).json()["data"])
    sid = next(s["id"] for s in elig if s["name"] == "答辩甲")

    assigned = client.post(f"{DG}/{gid}/assign", headers=h, params={"batchId": bid}, json={"studentIds": [str(sid)]}).json()["data"]
    assert any(s["id"] == str(sid) for s in assigned["students"])
    assert assigned["conflict"]

    blocked = client.post(f"{DG}/{gid}/publish", headers=h, params={"batchId": bid})
    assert blocked.json()["code"] != 0

    fixed = client.put(f"{DG}/{gid}", headers=h, params={"batchId": bid}, json={"groupName": "答辩组乙",
                       "chairMentorId": chair_id, "secretaryMentorId": secretary_id,
                       "defenseDate": "2026-06-20 09:00", "location": "B201",
                       "memberMentorIds": [judge_y_id, judge_x_id]}).json()["data"]
    assert fixed["conflict"] == ""
    assert any(s["id"] == str(sid) for s in fixed["students"])

    pub = client.post(f"{DG}/{gid}/publish", headers=h, params={"batchId": bid})
    assert pub.json()["code"] == 0
    assert pub.json()["data"]["published"] is True


def test_publish_requires_students(client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(client, h, "GD-DF-NS")
    chair_id = _mentor_id("组长C")
    secretary_id = _mentor_id("秘书C")
    judge_id = _mentor_id("评委M")
    grp = client.post(DG, headers=h, params={"batchId": bid}, json={"groupName": "答辩组丙", "batchId": bid, "chair": "组长C",
                                           "defenseDate": "2026-06-21 09:00", "location": "C101",
                                           "chairMentorId": chair_id, "memberMentorIds": [judge_id],
                                           "secretary": "秘书C", "secretaryMentorId": secretary_id}).json()["data"]
    no_stu = client.post(f"{DG}/{grp['id']}/publish", headers=h, params={"batchId": bid})
    assert no_stu.json()["code"] != 0


def test_export_and_student_view(client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(client, h, "GD-DF-EX")
    chair_id = _mentor_id("组长D")
    secretary_id = _mentor_id("秘书D")
    judge_a_id = _mentor_id("评委甲")
    judge_b_id = _mentor_id("评委乙")
    grp = client.post(DG, headers=h, params={"batchId": bid}, json={"groupName": "答辩组丁", "batchId": bid, "chair": "组长D",
                                           "defenseDate": "2026-06-22 09:00", "location": "D505",
                                           "chairMentorId": chair_id, "memberMentorIds": [judge_a_id, judge_b_id],
                                           "secretary": "秘书D", "secretaryMentorId": secretary_id}).json()["data"]
    gid = grp["id"]
    _student_with_advisor(client, h, "DF401", "答辩戊", "王导师", bid)
    _force_final_check("答辩戊")
    elig = _items(client.get(f"{DG}/eligible-students", headers=h, params={"gid": gid}).json()["data"])
    sid = next(s["id"] for s in elig if s["name"] == "答辩戊")
    client.post(f"{DG}/{gid}/assign", headers=h, params={"batchId": bid}, json={"studentIds": [str(sid)]})

    sh = _stu_token("答辩戊")
    before = client.get(f"{MOBILE}/graduation/defense", headers=sh).json()["data"]
    assert before["assigned"] is True and before["published"] is False

    client.post(f"{DG}/{gid}/publish", headers=h, params={"batchId": bid})
    after = client.get(f"{MOBILE}/graduation/defense", headers=sh).json()["data"]
    assert after["published"] is True
    assert after["location"] == "D505"

    exp = client.post(f"{DG}/export", headers=h, params={"batchId": bid})
    assert exp.json()["code"] == 0
    assert exp.json()["data"]["rowCount"] >= 1
