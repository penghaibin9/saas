"""考务管理（/academic-affairs/exam/*、/deferred-exams*）端点测试（SM-10）。

覆盖：批次生命周期(建→圈课→确认→推进→发布→结束→归档)、监考同时段冲突409、
无课程推进400、座位铺位+容量超限409、缺考登记触发风险位、缓考四级审批全链路、缓考重复申请409。
MySQL-only（db_mode 夹具）。口径核对施工包 §7/§9/§10。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (AaClassroom, AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm,
                            College, Major, SchoolClass, StudentProfile)
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    for code, name in (("101", "A101"), ("102", "A102"), ("201", "小教室")):
        db.add(AaClassroom(tenant_id=TID, building_code="A", building_name="A楼", room_code=code,
                           room_name=name, capacity=50, status="AVAILABLE"))
    db.flush()
    co1 = AaCourse(tenant_id=TID, course_code="EX_MATH", course_name="高等数学", credit=4, status="ENABLED")
    co2 = AaCourse(tenant_id=TID, course_code="EX_ENG", course_name="大学英语", credit=3, status="ENABLED")
    db.add_all([co1, co2]); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="2024秋教学任务",
                             college_id=col.id, status="ACTIVE")
    db.add(tb); db.flush()
    tt1 = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=co1.id, course_name="高等数学",
                         class_id=klass.id, teaching_class_name="软件2401",
                         teacher_key="teacher_a", teacher_name="甲老师")
    tt2 = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=co2.id, course_name="大学英语",
                         class_id=klass.id, teaching_class_name="软件2401",
                         teacher_key="teacher_b", teacher_name="乙老师")
    db.add_all([tt1, tt2]); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="EX2401", real_name="考甲", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024", student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="EX2402", real_name="考乙", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add_all([s1, s2]); db.flush()
    ids = {"tt1": tt1.id, "tt2": tt2.id, "s1": s1.id, "s2": s2.id, "college": col.id,
           "term": term.id}
    db.commit(); db.close()
    return ids


def _batch_with_confirmed_course(client, admin, tt_id, name="2024秋期末", term_id=None):
    """建批次→圈课→确认课程→推进 COURSE_CONFIRMED，返回 (batchId, examCourseId)。"""
    body = {"batchName": name}
    if term_id:
        body["termId"] = str(term_id)
    bid = client.post(f"{BASE}/exam/batches", headers=admin, json=body).json()["data"]["batchId"]
    cid = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin,
                      json={"teachingTaskId": str(tt_id)}).json()["data"]["examCourseId"]
    client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=admin, json={"action": "CONFIRM"})
    client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
               json={"examDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00", "durationMinutes": 120})
    client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    return bid, cid


def _mark_remaining_seats_present(exam_course_id):
    """finish closure gate 要求本场所有座位已有到考事实；未登记异常者按正常到考收口。"""
    from app.db.session import get_sessionmaker
    from app.models import AaExamRoomStudent

    db = get_sessionmaker()()
    db.query(AaExamRoomStudent).filter(
        AaExamRoomStudent.tenant_id == TID,
        AaExamRoomStudent.exam_course_id == int(exam_course_id),
        AaExamRoomStudent.attendance_status == "NOT_STARTED",
        AaExamRoomStudent.is_deleted.is_(False),
    ).update({"attendance_status": "PRESENT"}, synchronize_session=False)
    db.commit()
    db.close()


def test_e1_full_lifecycle(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], term_id=ids["term"])
    b = client.get(f"{BASE}/exam/batches/{bid}", headers=admin).json()["data"]
    assert b["status"] == "COURSE_CONFIRMED"
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    seat = client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                       json={"studentIds": [str(ids["s1"]), str(ids["s2"])]}).json()
    assert seat["data"]["seatCount"] == 2
    assert client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                       json={"teacherKey": "teacher_a", "teacherName": "甲老师", "role": "CHIEF"}).json()["code"] == 0
    assert client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin).json()["data"]["status"] == "PUBLISHED"
    _mark_remaining_seats_present(cid)
    assert client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin).json()["data"]["status"] == "FINISHED"
    assert client.post(f"{BASE}/exam/batches/{bid}/archive", headers=admin).json()["data"]["status"] == "ARCHIVED"


def test_e2_confirm_without_course_400(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/exam/batches", headers=admin,
                      json={"batchName": "空考试批次", "termId": str(ids["term"])}).json()["data"]["batchId"]
    assert client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin).status_code == 400


def test_e3_invigilator_conflict_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid1, cid1 = _batch_with_confirmed_course(client, admin, ids["tt1"], "批次A", term_id=ids["term"])
    bid2, cid2 = _batch_with_confirmed_course(client, admin, ids["tt2"], "批次B", term_id=ids["term"])
    r1 = client.post(f"{BASE}/exam/courses/{cid1}/rooms", headers=admin, json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    r2 = client.post(f"{BASE}/exam/courses/{cid2}/rooms", headers=admin, json={"classroomText": "A102", "capacity": 50}).json()["data"]["examRoomId"]
    assert client.post(f"{BASE}/exam/rooms/{r1}/invigilators", headers=admin,
                       json={"teacherKey": "teacher_a", "teacherName": "甲老师"}).json()["code"] == 0
    assert client.post(f"{BASE}/exam/rooms/{r2}/invigilators", headers=admin,
                       json={"teacherKey": "teacher_a", "teacherName": "甲老师"}).status_code == 409


def test_e4_seat_capacity_exceed_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], term_id=ids["term"])
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": "小教室", "capacity": 1}).json()["data"]["examRoomId"]
    assert client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                       json={"studentIds": [str(ids["s1"]), str(ids["s2"])]}).status_code == 409


def _fully_arrange(client, admin, cid, ids):
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin, json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s1"]), str(ids["s2"])]})
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin, json={"teacherKey": "teacher_x", "teacherName": "监考老师"})
    return rid


def test_e5_incident_absent_triggers_risk(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], term_id=ids["term"])
    _fully_arrange(client, admin, cid, ids)
    client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    r = client.post(f"{BASE}/exam/incidents", headers=admin,
                    json={"examCourseId": str(cid), "studentId": str(ids["s1"]), "incidentType": "ABSENT"}).json()
    assert r["code"] == 0 and r["data"]["riskAlertSent"] is True
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord
    db = get_sessionmaker()()
    risk = db.query(AffairsRiskRecord).filter(AffairsRiskRecord.tenant_id == TID,
                                              AffairsRiskRecord.source == "EXAM_ABSENT",
                                              AffairsRiskRecord.student_id == ids["s1"]).first()
    assert risk is not None and risk.status == "NEW"
    db.close()


def test_e9_publish_incomplete_arrangement_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], term_id=ids["term"])
    client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin, json={"classroomText": "A101", "capacity": 50})
    assert client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin).status_code == 409


def test_e10_patrol_conflict_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], term_id=ids["term"])
    p = {"teacherKey": "patrol_a", "teacherName": "巡考甲", "patrolDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00"}
    assert client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json=p).json()["code"] == 0
    p2 = dict(p, startTime="10:00", endTime="12:00")
    assert client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json=p2).status_code == 409


def test_e6_deferred_four_level_approval(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], term_id=ids["term"])
    stu = _stu_token("考甲", "EX2401")
    d = client.post(f"{BASE}/deferred-exams", headers=stu,
                    json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"}).json()
    assert d["code"] == 0
    did = d["data"]["deferId"]
    assert d["data"]["status"] == "COUNSELOR_REVIEW"
    r1 = client.post(f"{BASE}/deferred-exams/{did}/counselor-review", headers=admin, json={"action": "APPROVE"}).json()
    assert r1["data"]["status"] == "TEACHER_CONFIRM"
    r2 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=admin, json={"action": "APPROVE"}).json()
    assert r2["data"]["status"] == "COLLEGE_REVIEW"
    r3 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=admin, json={"action": "APPROVE"}).json()
    assert r3["data"]["status"] == "ACADEMIC_FINAL"
    r4 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=admin, json={"action": "APPROVE"}).json()
    assert r4["data"]["status"] == "APPROVED"


def test_e7_deferred_duplicate_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt2"], "缓考重复批次", term_id=ids["term"])
    stu = _stu_token("考甲", "EX2401")
    assert client.post(f"{BASE}/deferred-exams", headers=stu,
                       json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"}).json()["code"] == 0
    assert client.post(f"{BASE}/deferred-exams", headers=stu,
                       json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"}).status_code == 409


def test_e8_student_cannot_manage_batch_403(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("考甲", "EX2401")
    assert client.post(f"{BASE}/exam/batches", headers=stu, json={"batchName": "越权"}).status_code == 403


def test_e11_archived_readonly_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], term_id=ids["term"])
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin, json={"teacherKey": "teacher_z", "teacherName": "Z"})
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                json={"studentIds": [str(ids["s1"]), str(ids["s2"])]})
    pub = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    assert pub.status_code == 200 and pub.json()["data"]["status"] == "PUBLISHED"
    _mark_remaining_seats_present(cid)
    assert client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/exam/batches/{bid}/archive", headers=admin).json()["data"]["status"] == "ARCHIVED"
    r1 = client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s2"])]})
    assert r1.status_code == 409 and r1.json()["bizCode"] == "ARCHIVED_READONLY"
    r2 = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin, json={"classroomText": "B101", "capacity": 10})
    assert r2.status_code == 409 and r2.json()["bizCode"] == "ARCHIVED_READONLY"
    r3 = client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin, json={"teacherKey": "teacher_y"})
    assert r3.status_code == 409 and r3.json()["bizCode"] == "ARCHIVED_READONLY"
    r4 = client.post(f"{BASE}/exam/incidents", headers=admin,
                     json={"examCourseId": str(cid), "studentId": str(ids["s1"]), "incidentType": "ABSENT"})
    assert r4.status_code == 409 and r4.json()["bizCode"] == "ARCHIVED_READONLY"


def test_e12_archive_permission_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], term_id=ids["term"])
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin, json={"teacherKey": "teacher_z"})
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s1"])]})
    client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin)
    college_admin = _hdr(client, "college_admin01")
    assert client.post(f"{BASE}/exam/batches/{bid}/archive", headers=college_admin).status_code == 403


def test_e13_archive_list_readonly(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], "待归档批次", term_id=ids["term"])
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin, json={"teacherKey": "teacher_z"})
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                json={"studentIds": [str(ids["s1"]), str(ids["s2"])]})
    pub = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    assert pub.status_code == 200 and pub.json()["data"]["status"] == "PUBLISHED"
    _mark_remaining_seats_present(cid)
    assert client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin).status_code == 200
    bid2, _ = _batch_with_confirmed_course(client, admin, ids["tt2"], "未归档对照批次", term_id=ids["term"])
    assert client.post(f"{BASE}/exam/batches/{bid}/archive", headers=admin).status_code == 200
    r = client.get(f"{BASE}/exam/archive", headers=admin)
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    ids_in_list = {i["batchId"] for i in items}
    assert str(bid) in ids_in_list and str(bid2) not in ids_in_list
    row = [i for i in items if i["batchId"] == str(bid)][0]
    assert row["archivedAt"] and row["completenessSummary"]["courseCount"] == 1


def test_e14_defer_teacher_scope_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], "教师范围测试批次", term_id=ids["term"])
    stu = _stu_token("考甲", "EX2401")
    d = client.post(f"{BASE}/deferred-exams", headers=stu,
                    json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"}).json()
    did = d["data"]["deferId"]
    r1 = client.post(f"{BASE}/deferred-exams/{did}/counselor-review", headers=admin, json={"action": "APPROVE"}).json()
    assert r1["data"]["status"] == "TEACHER_CONFIRM"
    other_teacher = _hdr(client, "academic01")
    r2 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=other_teacher, json={"action": "APPROVE"})
    assert r2.status_code == 403


def test_e15_defer_counselor_scope_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt2"], "辅导员范围测试批次", term_id=ids["term"])
    stu = _stu_token("考甲", "EX2401")
    d = client.post(f"{BASE}/deferred-exams", headers=stu,
                    json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"}).json()
    did = d["data"]["deferId"]
    counselor = _hdr(client, "counselor01")
    r = client.post(f"{BASE}/deferred-exams/{did}/counselor-review", headers=counselor, json={"action": "APPROVE"})
    assert r.status_code == 403


def test_e16_defer_college_scope_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], "学院范围测试批次", term_id=ids["term"])
    stu = _stu_token("考甲", "EX2401")
    d = client.post(f"{BASE}/deferred-exams", headers=stu,
                    json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"}).json()
    did = d["data"]["deferId"]
    r1 = client.post(f"{BASE}/deferred-exams/{did}/counselor-review", headers=admin, json={"action": "APPROVE"}).json()
    assert r1["data"]["status"] == "TEACHER_CONFIRM"
    r2 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=admin, json={"action": "APPROVE"}).json()
    assert r2["data"]["status"] == "COLLEGE_REVIEW"
    college_admin = _hdr(client, "college_admin01")
    r3 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=college_admin, json={"action": "APPROVE"})
    assert r3.status_code == 403
