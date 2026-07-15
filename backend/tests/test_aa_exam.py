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
    from app.models import (AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm, College, Major,
                            SchoolClass, StudentProfile)
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
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
    ids = {"tt1": tt1.id, "tt2": tt2.id, "s1": s1.id, "s2": s2.id, "college": col.id}
    db.commit(); db.close()
    return ids


def _batch_with_confirmed_course(client, admin, tt_id, name="2024秋期末"):
    """建批次→圈课→确认课程→推进 COURSE_CONFIRMED，返回 (batchId, examCourseId)。"""
    bid = client.post(f"{BASE}/exam/batches", headers=admin, json={"batchName": name}).json()["data"]["batchId"]
    cid = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin,
                      json={"teachingTaskId": str(tt_id)}).json()["data"]["examCourseId"]
    client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=admin, json={"action": "CONFIRM"})
    # 未来考试日期：缓考「未开考」前置校验依赖此，冲突检测依赖同日同时段（两课程用同日即冲突）
    client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
               json={"examDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00", "durationMinutes": 120})
    client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    return bid, cid


def test_e1_full_lifecycle(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"])
    b = client.get(f"{BASE}/exam/batches/{bid}", headers=admin).json()["data"]
    assert b["status"] == "COURSE_CONFIRMED"
    # 加考场 + 铺位
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    seat = client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                       json={"studentIds": [str(ids["s1"]), str(ids["s2"])]}).json()
    assert seat["data"]["seatCount"] == 2
    # 监考
    assert client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                       json={"teacherKey": "teacher_a", "teacherName": "甲老师", "role": "CHIEF"}).json()["code"] == 0
    # 发布→结束→归档
    assert client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin).json()["data"]["status"] == "PUBLISHED"
    assert client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin).json()["data"]["status"] == "FINISHED"
    assert client.post(f"{BASE}/exam/batches/{bid}/archive", headers=admin).json()["data"]["status"] == "ARCHIVED"


def test_e2_confirm_without_course_400(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/exam/batches", headers=admin, json={"batchName": "空考试批次"}).json()["data"]["batchId"]
    assert client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin).status_code == 400


def test_e3_invigilator_conflict_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 两门课同一天同一时段
    bid1, cid1 = _batch_with_confirmed_course(client, admin, ids["tt1"], "批次A")
    bid2, cid2 = _batch_with_confirmed_course(client, admin, ids["tt2"], "批次B")
    r1 = client.post(f"{BASE}/exam/courses/{cid1}/rooms", headers=admin, json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    r2 = client.post(f"{BASE}/exam/courses/{cid2}/rooms", headers=admin, json={"classroomText": "A102", "capacity": 50}).json()["data"]["examRoomId"]
    # teacher_a 监考 r1（09:00-11:00）
    assert client.post(f"{BASE}/exam/rooms/{r1}/invigilators", headers=admin,
                       json={"teacherKey": "teacher_a", "teacherName": "甲老师"}).json()["code"] == 0
    # teacher_a 再监考 r2 同时段 → 409
    assert client.post(f"{BASE}/exam/rooms/{r2}/invigilators", headers=admin,
                       json={"teacherKey": "teacher_a", "teacherName": "甲老师"}).status_code == 409


def test_e4_seat_capacity_exceed_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"])
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": "小教室", "capacity": 1}).json()["data"]["examRoomId"]
    assert client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                       json={"studentIds": [str(ids["s1"]), str(ids["s2"])]}).status_code == 409


def _fully_arrange(client, admin, cid, ids):
    """加考场+铺位+监考，使课程编排完整（可发布）。返回 roomId。"""
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin, json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s1"]), str(ids["s2"])]})
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin, json={"teacherKey": "teacher_x", "teacherName": "监考老师"})
    return rid


def test_e5_incident_absent_triggers_risk(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"])
    _fully_arrange(client, admin, cid, ids)
    client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    r = client.post(f"{BASE}/exam/incidents", headers=admin,
                    json={"examCourseId": str(cid), "studentId": str(ids["s1"]), "incidentType": "ABSENT"}).json()
    assert r["code"] == 0 and r["data"]["riskAlertSent"] is True
    # 缺考真联动学工：写了 AffairsRiskRecord
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
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"])
    # 只加考场，不铺位不监考 → 发布应 409（编排不完整）
    client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin, json={"classroomText": "A101", "capacity": 50})
    assert client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin).status_code == 409


def test_e10_patrol_conflict_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"])
    p = {"teacherKey": "patrol_a", "teacherName": "巡考甲", "patrolDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00"}
    assert client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json=p).json()["code"] == 0
    # 同教师同日重叠时段 → 409
    p2 = dict(p, startTime="10:00", endTime="12:00")
    assert client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json=p2).status_code == 409


def test_e6_deferred_four_level_approval(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"])  # 未来考试日期，未开考可申请
    stu = _stu_token("考甲", "EX2401")
    d = client.post(f"{BASE}/deferred-exams", headers=stu,
                    json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"}).json()
    assert d["code"] == 0
    did = d["data"]["deferId"]
    assert d["data"]["status"] == "COUNSELOR_REVIEW"
    # 辅导员首审（school_admin01 走 review 通用节点亦可，但辅导员节点用 counselor-review）
    r1 = client.post(f"{BASE}/deferred-exams/{did}/counselor-review", headers=admin, json={"action": "APPROVE"}).json()
    assert r1["data"]["status"] == "TEACHER_CONFIRM"
    # 任课教师
    r2 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=admin, json={"action": "APPROVE"}).json()
    assert r2["data"]["status"] == "COLLEGE_REVIEW"
    # 学院
    r3 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=admin, json={"action": "APPROVE"}).json()
    assert r3["data"]["status"] == "ACADEMIC_FINAL"
    # 教务处终审
    r4 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=admin, json={"action": "APPROVE"}).json()
    assert r4["data"]["status"] == "APPROVED"


def test_e7_deferred_duplicate_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt2"], "缓考重复批次")
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
    """12号卡「考务归档」：ARCHIVED 批次任何写操作（含04-09号卡端点）一律 409 ARCHIVED_READONLY。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"])
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin, json={"teacherKey": "teacher_z", "teacherName": "Z"})
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s1"])]})
    client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin)
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
    """12号卡 T-PERM：归档动作仅教务处专属，学院教务 403（既有 _require_school，回归验证）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"])
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin, json={"teacherKey": "teacher_z"})
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s1"])]})
    client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin)
    college_admin = _hdr(client, "college_admin01")
    assert client.post(f"{BASE}/exam/batches/{bid}/archive", headers=college_admin).status_code == 403


def test_e13_archive_list_readonly(client, db_mode):
    """12号卡：GET /exam/archive 只返回 ARCHIVED 批次，含 archivedAt/completenessSummary。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], "待归档批次")
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": "A101", "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin, json={"teacherKey": "teacher_z"})
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s1"])]})
    client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin)
    # 另建一个不归档的批次做对照
    bid2, _ = _batch_with_confirmed_course(client, admin, ids["tt2"], "未归档对照批次")
    client.post(f"{BASE}/exam/batches/{bid}/archive", headers=admin)
    r = client.get(f"{BASE}/exam/archive", headers=admin)
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    ids_in_list = {i["batchId"] for i in items}
    assert str(bid) in ids_in_list and str(bid2) not in ids_in_list
    row = [i for i in items if i["batchId"] == str(bid)][0]
    assert row["archivedAt"] and row["completenessSummary"]["courseCount"] == 1


def test_e14_defer_teacher_scope_403(client, db_mode):
    """缓考审批节点级范围收敛：非本人授课教师在 TEACHER_CONFIRM 节点审批 → 403（不可越权代替真正任课教师）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # tt1 授课教师为 teacher_a，非 academic01
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], "教师范围测试批次")
    stu = _stu_token("考甲", "EX2401")
    d = client.post(f"{BASE}/deferred-exams", headers=stu,
                    json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"}).json()
    did = d["data"]["deferId"]
    # 辅导员节点先由 admin 放行到 TEACHER_CONFIRM
    r1 = client.post(f"{BASE}/deferred-exams/{did}/counselor-review", headers=admin, json={"action": "APPROVE"}).json()
    assert r1["data"]["status"] == "TEACHER_CONFIRM"
    other_teacher = _hdr(client, "academic01")
    r2 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=other_teacher, json={"action": "APPROVE"})
    assert r2.status_code == 403


def test_e15_defer_counselor_scope_403(client, db_mode):
    """缓考审批节点级范围收敛：辅导员未配置该学生所在班级授权 → COUNSELOR_REVIEW 节点 403。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt2"], "辅导员范围测试批次")
    stu = _stu_token("考甲", "EX2401")
    d = client.post(f"{BASE}/deferred-exams", headers=stu,
                    json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"}).json()
    did = d["data"]["deferId"]
    counselor = _hdr(client, "counselor01")  # 未配置 TeacherStudentScope，范围为空
    r = client.post(f"{BASE}/deferred-exams/{did}/counselor-review", headers=counselor, json={"action": "APPROVE"})
    assert r.status_code == 403
