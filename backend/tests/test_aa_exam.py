"""考务管理（/academic-affairs/exam/*、/deferred-exams*）端点测试（SM-10）。

覆盖：批次生命周期(建→圈课→确认→推进→发布→结束→归档)、监考同时段冲突409、
无课程推进400、座位铺位+容量超限409、缺考登记触发风险位、缓考四级审批全链路、缓考重复申请409。
MySQL-only（db_mode 夹具）。口径核对施工包 §7/§9/§10。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    response = client.post("/api/v1/auth/mock-login", json={"loginName": login_name, "password": "any"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed_exam_review_identity(db, college_id):
    """真实账号持有考务具体权限；学院确认与学校发布分别落到有效任职。"""
    from datetime import datetime
    from app.models import College, Role, RoleAssignmentScope, RolePermission, StaffAssignment, TeacherStudentScope, Tenant, User, UserRole
    from tests.support_grade_review_identity import _ensure_account, _ensure_permission, _ensure_college_assignment

    college = db.get(College, int(college_id))
    if db.get(Tenant, TID) is None:
        db.add(Tenant(id=TID, tenant_code="demo", school_name="考务责任回归学校", status="ACTIVE"))
    for login, scope_type, permissions in (
        ("college_admin01", "COLLEGE", ("view", "manage")),
        ("school_admin01", "SCHOOL", ("view", "manage", "arrange", "publish")),
    ):
        user = _ensure_account(db, login)
        role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == f"TEST_GRADE_{login.upper()}").one()
        link = db.query(UserRole).filter(UserRole.tenant_id == TID, UserRole.user_id == user.id, UserRole.role_id == role.id).one()
        task_actions = ("view", "manage", "confirm") if scope_type == "COLLEGE" else ("view", "confirm")
        codes = ["academicAffairs.exam." + action for action in permissions]
        codes += ["academicAffairs.teachingTask." + action for action in task_actions]
        for code in codes:
            permission = _ensure_permission(db, code)
            if not db.query(RolePermission).filter(RolePermission.tenant_id == TID,
                    RolePermission.role_id == role.id, RolePermission.permission_id == permission.id).first():
                db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status="ACTIVE"))
        scope_id = college.id if scope_type == "COLLEGE" else 0
        if not db.query(RoleAssignmentScope).filter(RoleAssignmentScope.tenant_id == TID,
                RoleAssignmentScope.user_role_id == link.id, RoleAssignmentScope.scope_type == scope_type).first():
            db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=link.id, user_id=user.id, role_code=role.role_code,
                scope_type=scope_type, scope_id=scope_id, effective_at=datetime(2020, 1, 1), status="ACTIVE"))
        if scope_type == "COLLEGE":
            college.secretary_id = user.id
            _ensure_college_assignment(db, user.id, college.id)
            if not db.query(TeacherStudentScope).filter(TeacherStudentScope.tenant_id == TID,
                    TeacherStudentScope.teacher_key == login, TeacherStudentScope.role_code == "COLLEGE_ADMIN",
                    TeacherStudentScope.scope_type == "COLLEGE", TeacherStudentScope.ref_value == college.college_name).first():
                db.add(TeacherStudentScope(tenant_id=TID, teacher_key=login, role_code="COLLEGE_ADMIN",
                    scope_type="COLLEGE", ref_value=college.college_name, status="ACTIVE"))
        elif not db.query(StaffAssignment).filter(StaffAssignment.tenant_id == TID, StaffAssignment.user_id == user.id,
                StaffAssignment.org_type == "SCHOOL", StaffAssignment.org_node_id == TID,
                StaffAssignment.assignment_type == "ACADEMIC_REVIEWER").first():
            db.add(StaffAssignment(tenant_id=TID, user_id=user.id, org_type="SCHOOL", org_node_id=TID,
                assignment_type="ACADEMIC_REVIEWER", effective_at=datetime(2020, 1, 1), status="ACTIVE"))
    teacher_role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == "ACADEMIC_TEACHER").first()
    if teacher_role is None:
        teacher_role = Role(tenant_id=TID, role_code="ACADEMIC_TEACHER", role_name="任课教师", role_type="CUSTOM", status="ACTIVE")
        db.add(teacher_role)
        db.flush()
    for code in ("academicAffairs.teachingTask.view", "academicAffairs.teachingTask.confirm"):
        permission = _ensure_permission(db, code)
        if not db.query(RolePermission).filter(RolePermission.tenant_id == TID, RolePermission.role_id == teacher_role.id,
                RolePermission.permission_id == permission.id).first():
            db.add(RolePermission(tenant_id=TID, role_id=teacher_role.id, permission_id=permission.id, status="ACTIVE"))
    for login, name in (("teacher_a", "甲老师"), ("teacher_b", "乙老师"), ("academic01", "赵敏")):
        teacher = db.query(User).filter(User.tenant_id == TID, User.login_name == login).first()
        if teacher is None:
            teacher = User(tenant_id=TID, login_name=login, real_name=name, user_type="TEACHER", password_hash="x", status="ACTIVE")
            db.add(teacher)
            db.flush()
        if not db.query(UserRole).filter(UserRole.tenant_id == TID, UserRole.user_id == teacher.id,
                UserRole.role_id == teacher_role.id).first():
            db.add(UserRole(tenant_id=TID, user_id=teacher.id, role_id=teacher_role.id, status="ACTIVE"))
    db.flush()


def _prepare_task_batch_for_exam(client, school, task_id):
    """考务只种初始任务；学院分配、本人确认、院校确认全部经正式命令推进。"""
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskBatch, Role, User, UserRole
    from app.services.auth_service_db import _claims, _role_contexts
    with get_sessionmaker()() as db:
        task = db.query(AaTeachingTask).filter(AaTeachingTask.tenant_id == TID, AaTeachingTask.id == int(task_id)).one()
        batch = db.get(AaTeachingTaskBatch, int(task.batch_id))
        tasks = db.query(AaTeachingTask).filter(AaTeachingTask.tenant_id == TID, AaTeachingTask.batch_id == batch.id).order_by(AaTeachingTask.id).all()
        if batch.status == "APPROVED":
            assert all(row.status == "READY" for row in tasks)
            return
        assert batch.status == "DRAFT", batch.status
        batch_id = str(batch.id)
        teacher_role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == "ACADEMIC_TEACHER").one()
        pending = []
        for row in tasks:
            assert row.status == "PENDING_ASSIGN", row.status
            teacher = db.query(User).join(UserRole, UserRole.user_id == User.id).filter(User.tenant_id == TID,
                User.login_name == row.teacher_key, User.status == "ACTIVE", UserRole.tenant_id == TID,
                UserRole.role_id == teacher_role.id, UserRole.status == "ACTIVE").one()
            contexts = _role_contexts(db, teacher)
            context = next(item for item in contexts if item["contextId"] == f"role:{teacher_role.id}")
            token = create_access_token(_claims(db, teacher, context, contexts, "PC"))
            pending.append((str(row.id), teacher.login_name, teacher.real_name, {"Authorization": "Bearer " + token}))
    college = _hdr(client, "college_admin01")
    for current_id, teacher_key, teacher_name, teacher_headers in pending:
        assigned = client.post(f"{BASE}/teaching-tasks/{current_id}/assign", headers=college,
            json={"teacherKey": teacher_key, "teacherName": teacher_name})
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["data"]["teachingClassProjection"]["ok"] is True
        confirmed = client.post(f"{BASE}/teaching-tasks/{current_id}/teacher-act", headers=teacher_headers,
            json={"action": "CONFIRM"})
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["data"]["status"] == "TEACHER_CONFIRMED"
    submitted = client.post(f"{BASE}/teaching-task-batches/{batch_id}/submit", headers=college)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "COLLEGE_CONFIRMED"
    reviewed = client.post(f"{BASE}/teaching-task-batches/{batch_id}/review", headers=school, json={"action": "APPROVE"})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["status"] == "APPROVED"
    readback = client.get(f"{BASE}/teaching-task-batches/{batch_id}/tasks", headers=school)
    assert readback.status_code == 200, readback.text
    assert {row["taskId"]: row["status"] for row in readback.json()["data"]["items"]} == {
        current_id: "READY" for current_id, *_ in pending}


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
                             college_id=col.id, status="DRAFT")
    db.add(tb); db.flush()
    tt1 = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=co1.id, course_code=co1.course_code, course_name="高等数学",
                         class_id=klass.id, teaching_class_name="软件2401",
                         teacher_key="teacher_a", teacher_name="甲老师")
    tt2 = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=co2.id, course_code=co2.course_code, course_name="大学英语",
                         class_id=klass.id, teaching_class_name="软件2401",
                         teacher_key="teacher_b", teacher_name="乙老师")
    db.add_all([tt1, tt2]); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="EX2401", real_name="考甲", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024", student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="EX2402", real_name="考乙", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add_all([s1, s2]); db.flush()
    _seed_exam_review_identity(db, col.id)
    ids = {"tt1": tt1.id, "tt2": tt2.id, "s1": s1.id, "s2": s2.id, "college": col.id,
           "term": term.id}
    db.commit(); db.close()
    return ids


def _batch_with_confirmed_course(client, admin, tt_id, name="2024秋期末", term_id=None):
    """建批次→圈课→确认课程→推进 COURSE_CONFIRMED，返回 (batchId, examCourseId)。"""
    _prepare_task_batch_for_exam(client, admin, tt_id)
    body = {"batchName": name}
    if term_id:
        body["termId"] = str(term_id)
    created = client.post(f"{BASE}/exam/batches", headers=admin, json=body)
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["batchId"]
    added = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin, json={"teachingTaskId": str(tt_id)})
    assert added.status_code == 200, added.text
    cid = added.json()["data"]["examCourseId"]
    confirmed = client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=_hdr(client, "college_admin01"), json={"action": "CONFIRM"})
    assert confirmed.status_code == 200, confirmed.text
    scheduled = client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
               json={"examDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00", "durationMinutes": 120})
    assert scheduled.status_code == 200, scheduled.text
    advanced = client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    assert advanced.status_code == 200, advanced.text
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


def test_exam_batch_list_filters_term_before_count_and_keeps_college_scope(client, db_mode):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaExamBatch, AaExamCourse, AaTeachingTask, AaTerm, College

    ids = _seed(db_mode)
    with get_sessionmaker()() as db:
        task = db.get(AaTeachingTask, ids["tt1"])
        home_course = db.get(AaCourse, task.course_id)
        home_course.owner_college_id = ids["college"]
        later_term = AaTerm(tenant_id=TID, year_code="2025-2026", term_no=1,
                            status="PUBLISHED", is_current=False)
        foreign_college = College(tenant_id=TID, college_name="考务外院", status="ACTIVE")
        db.add_all([later_term, foreign_college])
        db.flush()
        foreign_course = AaCourse(tenant_id=TID, course_code="EX_FOREIGN_TERM",
                                  course_name="外院考试课程", owner_college_id=foreign_college.id,
                                  credit=2, status="ENABLED")
        db.add(foreign_course)
        db.flush()
        created = {}
        for name, term_id, course_id in (
            ("本院一期甲", ids["term"], home_course.id),
            ("本院一期乙", ids["term"], home_course.id),
            ("本院二期", later_term.id, home_course.id),
            ("外院二期", later_term.id, foreign_course.id),
        ):
            batch = AaExamBatch(tenant_id=TID, batch_name=name, term_id=term_id,
                                status="ARCHIVED", published_at=datetime(2026, 7, 1))
            db.add(batch)
            db.flush()
            db.add(AaExamCourse(tenant_id=TID, batch_id=batch.id, course_id=course_id,
                                course_name=name, status="CONFIRMED"))
            created[name] = str(batch.id)
        db.commit()
        later_term_id = later_term.id

    school = _hdr(client, "school_admin01")
    college = _hdr(client, "college_admin01")
    first = client.get(f"{BASE}/exam/batches", headers=school,
                       params={"termId": ids["term"], "page": 1, "pageSize": 1})
    second = client.get(f"{BASE}/exam/batches", headers=school,
                        params={"termId": ids["term"], "page": 2, "pageSize": 1})
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["total"] == second.json()["data"]["total"] == 2
    assert {first.json()["data"]["items"][0]["batchId"],
            second.json()["data"]["items"][0]["batchId"]} == {created["本院一期甲"], created["本院一期乙"]}
    later = client.get(f"{BASE}/exam/batches", headers=college,
                       params={"termId": later_term_id, "pageSize": 1})
    assert later.status_code == 200
    assert later.json()["data"]["total"] == 1
    assert [row["batchId"] for row in later.json()["data"]["items"]] == [created["本院二期"]]
    all_terms = client.get(f"{BASE}/exam/batches", headers=school)
    assert all_terms.status_code == 200 and all_terms.json()["data"]["total"] == 4
    for invalid in ("0", "-1", "abc"):
        assert client.get(f"{BASE}/exam/batches", headers=school,
                          params={"termId": invalid}).status_code == 422


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
    # 课程确认已由真实本院办理人完成；此负向用例将其当前范围调到另一学院，
    # 保留“学院不能审核外院课程”的原断言，而不是依赖没有任何学院范围的空身份。
    from app.db.session import get_sessionmaker
    from app.models import College, RoleAssignmentScope, TeacherStudentScope, User
    with get_sessionmaker()() as db:
        other = College(tenant_id=TID, college_name="考务范围对照学院", status="ACTIVE")
        db.add(other)
        db.flush()
        uid = db.query(User.id).filter(User.tenant_id == TID, User.login_name == "college_admin01").scalar()
        db.query(TeacherStudentScope).filter(TeacherStudentScope.tenant_id == TID,
            TeacherStudentScope.teacher_key == "college_admin01", TeacherStudentScope.scope_type == "COLLEGE").update(
                {"ref_value": other.college_name}, synchronize_session=False)
        db.query(RoleAssignmentScope).filter(RoleAssignmentScope.tenant_id == TID,
            RoleAssignmentScope.user_id == uid, RoleAssignmentScope.scope_type == "COLLEGE").update(
                {"scope_id": other.id}, synchronize_session=False)
        db.commit()
    college_admin = _hdr(client, "college_admin01")
    r3 = client.post(f"{BASE}/deferred-exams/{did}/review", headers=college_admin, json={"action": "APPROVE"})
    assert r3.status_code == 403
