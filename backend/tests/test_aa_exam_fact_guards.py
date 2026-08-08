"""考务正式事实门禁回归（P0-D01 / P0-D02 / P0-D03 / P0-D04）。

这几条守卫的共同点：客户端传来的一个 id 或一次普通 UPDATE，过去可以直接变成学校的正式教务事实。
- D01 已发布/结束/归档批次的考试时间被直接改写；
- D03 非本场考生被登记缺考/违纪，进而生成学工风险；
- D04 非本场学生对该考试发起正式缓考审批；
- D02 两个批次各自内部合法，却把同一间教室/同一个学生/同一个老师排在同一时段。

每条都验证：合法路径仍然通；非法路径被 409 挡下（本项目冻结契约无 422 档，同类判定统一 DATA_CONFLICT/409）；且失败后主表、风险表、审计表零副作用。
守卫必须由公开 Facade 显式实现，不允许经 __getattr__ 落回 legacy——本文件用运行时 __module__ 断言，
不靠读源码字符串（读代码只能证明代码长什么样，证明不了运行时到底调用了谁）。
MySQL-only（db_mode 夹具）。
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
    other = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2402", grade="2024", status="ACTIVE")
    db.add_all([klass, other]); db.flush()
    course = AaCourse(tenant_id=TID, course_code="FG_MATH", course_name="高等数学", credit=4,
                      version=1, status="ENABLED")
    course2 = AaCourse(tenant_id=TID, course_code="FG_ENG", course_name="大学英语", credit=3,
                       version=1, status="ENABLED")
    db.add_all([course, course2]); db.flush()
    # 正式教室字典：发布门禁只认 canonical classroom_id，人工考场靠显示名精确回填
    room_a = AaClassroom(tenant_id=TID, building_code="A", building_name="A楼", room_code="101",
                         room_name="A101", capacity=50, status="AVAILABLE")
    room_b = AaClassroom(tenant_id=TID, building_code="A", building_name="A楼", room_code="102",
                         room_name="A102", capacity=50, status="AVAILABLE")
    db.add_all([room_a, room_b]); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="2024秋教学任务",
                             college_id=col.id, status="ACTIVE")
    db.add(tb); db.flush()
    task = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=course.id, course_name="高等数学",
                          class_id=klass.id, teaching_class_name="软件2401",
                          teacher_key="teacher_a", teacher_name="甲老师")
    # task2 同班开设：名单与 task 完全相同，用来构造「同一个学生被排两场」
    task2 = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=course2.id, course_name="大学英语",
                           class_id=klass.id, teaching_class_name="软件2401",
                           teacher_key="teacher_b", teacher_name="乙老师")
    # task3 开在另一个行政班：名单与 task 不相交，用来单独构造教室/监考竞争而不掺入学生冲突
    task3 = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=course2.id, course_name="大学英语",
                           class_id=other.id, teaching_class_name="软件2402",
                           teacher_key="teacher_c", teacher_name="丙老师")
    db.add_all([task, task2, task3]); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="FG2401", real_name="考甲", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="FG2402", real_name="考乙", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    # 外班学生：从来不属于这门课的教学名单，是三条守卫的反向主角
    outsider = StudentProfile(tenant_id=TID, student_no="FG9999", real_name="外班丙", college_id=col.id,
                              major_id=major.id, class_id=other.id, grade="2024",
                              student_status="NORMAL", status="ACTIVE")
    db.add_all([s1, s2, outsider]); db.flush()
    ids = {"term": term.id, "task": task.id, "task2": task2.id, "task3": task3.id,
           "s1": s1.id, "s2": s2.id, "outsider": outsider.id, "college": col.id}
    db.commit(); db.close()
    return ids


def _confirmed_course(client, admin, ids, name="2024秋期末", *, task_key="task",
                      exam_date="2027-06-20", start="09:00", end="11:00"):
    """建批次→圈课→学院确认（冻结名单）→设时间→推进 COURSE_CONFIRMED。"""
    bid = client.post(f"{BASE}/exam/batches", headers=admin,
                      json={"batchName": name, "termId": str(ids["term"])}).json()["data"]["batchId"]
    cid = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin,
                      json={"teachingTaskId": str(ids[task_key])}).json()["data"]["examCourseId"]
    confirmed = client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=admin, json={"action": "CONFIRM"})
    assert confirmed.status_code == 200, confirmed.text
    client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
               json={"examDate": exam_date, "startTime": start, "endTime": end,
                     "durationMinutes": 120})
    client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    return bid, cid


def _arrange(client, admin, cid, ids, *, classroom="A101", invigilator="teacher_x",
             students=("s1", "s2")):
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomText": classroom, "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                json={"studentIds": [str(ids[key]) for key in students]})
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                json={"teacherKey": invigilator, "teacherName": "监考老师"})
    return rid


def _publish(client, admin, bid, cid, ids, **kwargs):
    rid = _arrange(client, admin, cid, ids, **kwargs)
    r = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    assert r.status_code == 200, r.text
    return rid


def test_guarded_commands_are_served_by_public_facade_at_runtime():
    """三条守卫必须是 Facade 显式实现；落回 legacy 就等于守卫没生效。"""
    import app.models  # noqa: F401  先建立模型注册，避免循环导入
    from app.modules.academic_affairs.services import academic_affairs_exam_facade as facade

    for name in ("set_course_schedule", "record_incident", "defer_apply"):
        assert getattr(facade, name).__module__.endswith("academic_affairs_exam_facade"), name


# ── P0-D01：已发布考试时间不可直接改写 ──

def test_d01_schedule_editable_before_publish(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, cid = _confirmed_course(client, admin, ids)
    r = client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
                   json={"examDate": "2027-06-21", "startTime": "14:00", "endTime": "16:00"})
    assert r.status_code == 200
    assert r.json()["data"]["examDate"] == "2027-06-21"


def test_d01_published_schedule_change_rejected_without_side_effect(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    _publish(client, admin, bid, cid, ids)

    r = client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
                   json={"examDate": "2027-06-25", "startTime": "14:00", "endTime": "16:00"})
    assert r.status_code == 409
    # 数据库时间必须一个字节没变
    from app.db.session import get_sessionmaker
    from app.models import AaExamAuditTrail, AaExamCourse
    db = get_sessionmaker()()
    course = db.get(AaExamCourse, int(cid))
    assert course.exam_date == "2027-06-20" and course.start_time == "09:00"
    # 失败不得留下"已设时间"的假成功审计
    trails = db.query(AaExamAuditTrail).filter(
        AaExamAuditTrail.tenant_id == TID, AaExamAuditTrail.biz_type == "EXAM_COURSE",
        AaExamAuditTrail.biz_id == int(cid), AaExamAuditTrail.action == "EXAM_COURSE_SCHEDULE",
    ).all()
    assert all("2027-06-25" not in (t.detail or "") for t in trails)
    db.close()


def test_d01_finished_and_archived_schedule_change_rejected(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    rid = _publish(client, admin, bid, cid, ids)
    # 收口后结束批次
    client.post(f"{BASE}/exam/incidents", headers=admin,
                json={"examCourseId": str(cid), "studentId": str(ids["s1"]), "incidentType": "ABSENT"})
    seats = client.get(f"{BASE}/exam/rooms/{rid}/seats", headers=admin).json()["data"]["items"]
    assert any(s["attendanceStatus"] == "ABSENT" for s in seats)
    from app.db.session import get_sessionmaker
    from app.models import AaExamRoomStudent
    db = get_sessionmaker()()
    db.query(AaExamRoomStudent).filter(
        AaExamRoomStudent.tenant_id == TID, AaExamRoomStudent.exam_course_id == int(cid),
        AaExamRoomStudent.attendance_status == "NOT_STARTED",
    ).update({"attendance_status": "PRESENT"}, synchronize_session=False)
    db.commit(); db.close()
    assert client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin).status_code == 200
    assert client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
                      json={"examDate": "2027-07-01"}).status_code == 409
    assert client.post(f"{BASE}/exam/batches/{bid}/archive", headers=admin).status_code == 200
    assert client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
                      json={"examDate": "2027-07-02"}).status_code == 409


# ── P0-D03：非本场考生不得被登记缺考/违纪 ──

def test_d03_incident_for_seated_student_succeeds(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    _publish(client, admin, bid, cid, ids)
    r = client.post(f"{BASE}/exam/incidents", headers=admin,
                    json={"examCourseId": str(cid), "studentId": str(ids["s1"]),
                          "incidentType": "ABSENT"}).json()
    assert r["code"] == 0 and r["data"]["riskAlertSent"] is True
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord
    db = get_sessionmaker()()
    risk = db.query(AffairsRiskRecord).filter(
        AffairsRiskRecord.tenant_id == TID, AffairsRiskRecord.source == "EXAM_ABSENT",
        AffairsRiskRecord.student_id == ids["s1"]).first()
    assert risk is not None and risk.status == "NEW"
    db.close()


def test_d03_incident_for_outsider_rejected_without_side_effect(client, db_mode):
    """外班学生根本不在本场座位名单，缺考登记必须 409，且不得污染学工风险。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    _publish(client, admin, bid, cid, ids)

    r = client.post(f"{BASE}/exam/incidents", headers=admin,
                    json={"examCourseId": str(cid), "studentId": str(ids["outsider"]),
                          "incidentType": "ABSENT"})
    assert r.status_code == 409

    from app.db.session import get_sessionmaker
    from app.models import AaExamAuditTrail, AaExamIncident, AffairsRiskRecord
    db = get_sessionmaker()()
    assert db.query(AaExamIncident).filter(
        AaExamIncident.tenant_id == TID,
        AaExamIncident.student_id == ids["outsider"]).count() == 0
    assert db.query(AffairsRiskRecord).filter(
        AffairsRiskRecord.tenant_id == TID, AffairsRiskRecord.source == "EXAM_ABSENT",
        AffairsRiskRecord.student_id == ids["outsider"]).count() == 0
    assert db.query(AaExamAuditTrail).filter(
        AaExamAuditTrail.tenant_id == TID,
        AaExamAuditTrail.action == "EXAM_INCIDENT_RECORD",
        AaExamAuditTrail.detail.like(f"%学生{ids['outsider']}%")).count() == 0
    db.close()


def test_d03_incident_violation_for_outsider_also_rejected(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    _publish(client, admin, bid, cid, ids)
    r = client.post(f"{BASE}/exam/incidents", headers=admin,
                    json={"examCourseId": str(cid), "studentId": str(ids["outsider"]),
                          "incidentType": "DISCIPLINE_VIOLATION", "description": "夹带"})
    assert r.status_code == 409


# ── P0-D04：缓考必须证明本人属于该考试正式名单 ──

def test_d04_defer_apply_for_roster_member_succeeds(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, cid = _confirmed_course(client, admin, ids)
    stu = _stu_token("考甲", "FG2401")
    d = client.post(f"{BASE}/deferred-exams", headers=stu,
                    json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"}).json()
    assert d["code"] == 0 and d["data"]["status"] == "COUNSELOR_REVIEW"
    # 同课程重复申请 → 409
    assert client.post(f"{BASE}/deferred-exams", headers=stu,
                       json={"examCourseId": str(cid), "reasonType": "SICK"}).status_code == 409


def test_d04_defer_apply_for_outsider_rejected_without_side_effect(client, db_mode):
    """外班学生知道 examCourseId 也不能对这门考试发起正式缓考审批。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, cid = _confirmed_course(client, admin, ids)
    outsider = _stu_token("外班丙", "FG9999")

    r = client.post(f"{BASE}/deferred-exams", headers=outsider,
                    json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院"})
    assert r.status_code == 409

    from app.db.session import get_sessionmaker
    from app.models import AaDeferredExam, AaExamAuditTrail
    db = get_sessionmaker()()
    assert db.query(AaDeferredExam).filter(
        AaDeferredExam.tenant_id == TID,
        AaDeferredExam.student_id == ids["outsider"]).count() == 0
    assert db.query(AaExamAuditTrail).filter(
        AaExamAuditTrail.tenant_id == TID,
        AaExamAuditTrail.action == "DEFER_APPLY_SUBMIT").count() == 0
    db.close()


# ── P0-D02：发布前全校资源冲突门禁 ──

def test_d02_publish_requires_canonical_classroom_identity(client, db_mode):
    """人工考场文本匹配不到正式教室时，教室冲突检测等于失效，必须在发布口挡下。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    _arrange(client, admin, cid, ids, classroom="第一教学楼301")  # 字典里没有这个显示名
    r = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    assert r.status_code == 409
    assert "CLASSROOM_IDENTITY_MISSING" in r.text
    from app.db.session import get_sessionmaker
    from app.models import AaExamBatch
    db = get_sessionmaker()()
    assert db.get(AaExamBatch, int(bid)).status == "COURSE_CONFIRMED"
    db.close()


def test_d02_room_conflict_across_batches_blocks_publish(client, db_mode):
    """A101 已被已发布批次在 09:00-11:00 占用，另一批次同时段再排同一间教室 → 409。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid1, cid1 = _confirmed_course(client, admin, ids, "批次A")
    _publish(client, admin, bid1, cid1, ids, classroom="A101")

    # 第二个批次：换课程、换学生、换监考，只有教室和时段与已发布批次相同
    bid2, cid2 = _confirmed_course(client, admin, ids, "批次B", task_key="task3")
    _arrange(client, admin, cid2, ids, classroom="A101", invigilator="teacher_y",
             students=("outsider",))
    r = client.post(f"{BASE}/exam/batches/{bid2}/publish", headers=admin)
    assert r.status_code == 409 and "ROOM_CONFLICT" in r.text
    # 换到 A102 即可发布，证明挡的是教室占用本身而不是别的原因
    from app.db.session import get_sessionmaker
    from app.models import AaExamRoom
    db = get_sessionmaker()()
    room = db.query(AaExamRoom).filter(AaExamRoom.tenant_id == TID,
                                       AaExamRoom.exam_course_id == int(cid2)).first()
    room_id = room.id
    db.close()
    client.post(f"{BASE}/exam/rooms/{room_id}/seats", headers=admin,
                json={"studentIds": [str(ids["outsider"])]})
    db = get_sessionmaker()()
    room = db.get(AaExamRoom, room_id)
    room.classroom_text = "A102"
    from app.models import AaClassroom
    room.classroom_id = db.query(AaClassroom).filter(
        AaClassroom.tenant_id == TID, AaClassroom.room_name == "A102").first().id
    db.commit(); db.close()
    assert client.post(f"{BASE}/exam/batches/{bid2}/publish", headers=admin).status_code == 200


def test_d02_student_exam_conflict_across_batches_blocks_publish(client, db_mode):
    """同一个学生在同一时段被排进两场考试 → 409，考生不可能分身。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid1, cid1 = _confirmed_course(client, admin, ids, "批次A")
    _publish(client, admin, bid1, cid1, ids, classroom="A101", students=("s1", "s2"))

    bid2, cid2 = _confirmed_course(client, admin, ids, "批次B", task_key="task2")
    # 换教室、换监考，只有考生与时段重叠
    _arrange(client, admin, cid2, ids, classroom="A102", invigilator="teacher_y",
             students=("s1", "s2"))
    r = client.post(f"{BASE}/exam/batches/{bid2}/publish", headers=admin)
    assert r.status_code == 409 and "STUDENT_EXAM_CONFLICT" in r.text


def test_d02_invigilator_conflict_across_batches_blocks_publish(client, db_mode):
    """同一个监考老师同时段被排两场 → 409。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid1, cid1 = _confirmed_course(client, admin, ids, "批次A")
    _publish(client, admin, bid1, cid1, ids, classroom="A101", invigilator="teacher_x")

    bid2, cid2 = _confirmed_course(client, admin, ids, "批次B", task_key="task3")
    rid2 = _arrange(client, admin, cid2, ids, classroom="A102", invigilator="teacher_y",
                    students=("outsider",))
    # 通过接口把 teacher_x 排进来会被既有的排监考冲突检测直接 409（第一道防线，本来就该拦）。
    # 发布门禁是第二道防线，防的是守卫上线前的存量安排和自动排考绕过，因此直接造库。
    from app.db.session import get_sessionmaker
    from app.models import AaExamInvigilator
    db = get_sessionmaker()()
    row = db.query(AaExamInvigilator).filter(
        AaExamInvigilator.tenant_id == TID, AaExamInvigilator.exam_room_id == int(rid2)).first()
    row.teacher_key = "teacher_x"
    db.commit(); db.close()
    r = client.post(f"{BASE}/exam/batches/{bid2}/publish", headers=admin)
    assert r.status_code == 409 and "INVIGILATOR_CONFLICT" in r.text


def test_d02_patrol_and_invigilation_share_one_teacher_timeline(client, db_mode):
    """同一个老师不能 09:00-11:00 监考、又 09:30-10:30 巡考——那是同一份时间。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    ids2 = ids
    bid, cid = _confirmed_course(client, admin, ids2)
    _arrange(client, admin, cid, ids2, classroom="A101", invigilator="teacher_x")
    # 走接口排这条巡考会被既有的排巡考冲突检测直接 409（那是第一道防线，本来就该拦）。
    # 发布门禁是第二道防线，防的是守卫上线前的存量数据和绕过接口写入的安排，因此直接造库。
    from app.db.session import get_sessionmaker
    from app.models import AaExamPatrol
    db = get_sessionmaker()()
    db.add(AaExamPatrol(tenant_id=TID, batch_id=int(bid), teacher_key="teacher_x",
                        teacher_name="监考老师", patrol_date="2027-06-20",
                        start_time="09:30", end_time="10:30", status="ASSIGNED"))
    db.commit(); db.close()
    r = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    assert r.status_code == 409 and "CONFLICT" in r.text


def test_d02_non_overlapping_resources_still_publish(client, db_mode):
    """同教室不同时段、同老师不同时段必须放行，门禁不能一刀切拦死正常排考。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid1, cid1 = _confirmed_course(client, admin, ids, "批次A")
    _publish(client, admin, bid1, cid1, ids, classroom="A101", invigilator="teacher_x")

    # 同教室同监考，但改到下午，与上午场不重叠
    bid2, cid2 = _confirmed_course(client, admin, ids, "批次B", task_key="task3",
                                   start="14:00", end="16:00")
    _arrange(client, admin, cid2, ids, classroom="A101", invigilator="teacher_x",
             students=("outsider",))
    assert client.post(f"{BASE}/exam/batches/{bid2}/publish", headers=admin).status_code == 200


def test_d02_concurrent_publish_of_same_resource_lets_only_one_win(client, db_mode):
    """真实 MySQL 并发：两个批次同时抢同一间教室同一时段，只能有一个 PUBLISHED。

    发布事务先取同学期批次行锁再检测，因此后到的事务必然看到先提交者的占用。
    """
    import threading

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid1, cid1 = _confirmed_course(client, admin, ids, "并发A")
    _arrange(client, admin, cid1, ids, classroom="A101", invigilator="teacher_x")
    bid2, cid2 = _confirmed_course(client, admin, ids, "并发B", task_key="task3")
    _arrange(client, admin, cid2, ids, classroom="A101", invigilator="teacher_y",
             students=("outsider",))

    results = {}
    barrier = threading.Barrier(2)

    def _publish_one(key, bid):
        barrier.wait()
        results[key] = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin).status_code

    threads = [threading.Thread(target=_publish_one, args=("a", bid1)),
               threading.Thread(target=_publish_one, args=("b", bid2))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    from app.db.session import get_sessionmaker
    from app.models import AaExamBatch
    db = get_sessionmaker()()
    published = [
        int(b.id) for b in db.query(AaExamBatch).filter(
            AaExamBatch.tenant_id == TID,
            AaExamBatch.id.in_([int(bid1), int(bid2)]),
            AaExamBatch.status == "PUBLISHED",
        ).all()
    ]
    db.close()
    assert len(published) == 1, f"两个批次抢同一教室，结果 {results}，已发布 {published}"
