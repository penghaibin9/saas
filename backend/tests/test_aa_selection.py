"""选课管理（/academic-affairs/selection/*）端点测试（SM-09 冻结状态机）。

历史夹具已对齐当前生产合同：正式 termId、真实学生账号绑定、StudentAcademicFact 自动基线、
稳定 courseCode、正式 READY 教学任务与名单锁定前置。业务状态机、容量、越权、冲突、锁定和归档断言保持原强度。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    """使用正式 DB 登录链生成 token，禁止测试自行伪造真实账号上下文。"""
    from app.services.auth_service_db import login_with_password

    data = login_with_password(student_no, "Test@123456", client_type="MP")
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, College, Major, Role, SchoolClass, StudentProfile, User, UserRole
    from app.services import student_account_link_service as link_service

    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    c1 = AaCourse(tenant_id=TID, course_code="SEL001", course_name="职业素养选修", credit=2, status="ENABLED")
    c2 = AaCourse(tenant_id=TID, course_code="SEL002", course_name="人工智能导论", credit=3, status="ENABLED")
    db.add_all([c1, c2]); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="SEL2401", real_name="选甲", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="SEL2402", real_name="选乙", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    s3 = StudentProfile(tenant_id=TID, student_no="SEL2403", real_name="休丙", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="SUSPENDED", status="ACTIVE")
    db.add_all([s1, s2, s3]); db.flush()

    student_role = db.query(Role).filter(
        Role.tenant_id == TID, Role.role_code == "STUDENT", Role.is_deleted.is_(False)
    ).first()
    if student_role is None:
        student_role = Role(tenant_id=TID, role_code="STUDENT", role_name="学生", status="ACTIVE")
        db.add(student_role); db.flush()
    else:
        student_role.status = "ACTIVE"

    for student in (s1, s2, s3):
        user = User(
            tenant_id=TID, login_name=student.student_no, real_name=student.real_name,
            password_hash=hash_password("Test@123456"), user_type="STUDENT", status="ACTIVE",
        )
        db.add(user); db.flush()
        db.add(UserRole(
            tenant_id=TID, user_id=int(user.id), role_id=int(student_role.id), status="ACTIVE"
        ))
        link_service.bind_in_session(
            db, tenant_id=TID, student_id=int(student.id), user_id=int(user.id),
            source="TEST_FIXTURE", login_name=student.student_no, student_no=student.student_no,
        )
    ids = {"course1": c1.id, "course2": c2.id, "s1": s1.id, "s2": s2.id, "s3": s3.id,
           "class": klass.id, "major": major.id, "college": col.id}
    db.commit(); db.close()
    return ids


def _ensure_term():
    """选课批次绑定正式、可写、已发布学期，不依赖 magic termId。"""
    from app.db.session import get_sessionmaker
    from app.models import AaTerm

    db = get_sessionmaker()()
    try:
        term = db.query(AaTerm).filter(
            AaTerm.tenant_id == TID,
            AaTerm.year_code == "2024-2025",
            AaTerm.term_no == 1,
            AaTerm.is_deleted.is_(False),
        ).first()
        if not term:
            term = AaTerm(
                tenant_id=TID, year_code="2024-2025", term_no=1,
                term_name="2024-2025第1学期", teaching_weeks=18,
                status="PUBLISHED", is_current=True,
            )
            db.add(term); db.flush()
        else:
            term.teaching_weeks = 18
            term.status = "PUBLISHED"
            term.is_current = True
        term_id = int(term.id)
        db.commit()
        return term_id
    finally:
        db.close()


def _ready_tasks(ids, *, with_conflict_slots=False):
    """名单锁定与冲突判断必须回链同学期的正式 READY 教学任务。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch, SchoolClass

    db = get_sessionmaker()()
    term_id = _ensure_term()
    klass = db.get(SchoolClass, int(ids["class"]))
    c1 = db.get(AaCourse, int(ids["course1"]))
    c2 = db.get(AaCourse, int(ids["course2"]))
    assert klass is not None and c1 is not None and c2 is not None
    seq = db.query(AaTeachingTaskBatch).filter(AaTeachingTaskBatch.tenant_id == TID).count() + 1
    batch = AaTeachingTaskBatch(
        tenant_id=TID, term_id=int(term_id), batch_name=f"选课回归教学任务批次-{seq}",
        college_id=int(ids["college"]), status="APPROVED",
    )
    db.add(batch); db.flush()
    tasks = []
    for idx, course in enumerate((c1, c2), start=1):
        task = AaTeachingTask(
            tenant_id=TID, batch_id=batch.id, course_id=course.id,
            course_code=course.course_code, course_name=course.course_name,
            class_id=int(ids["class"]), teaching_class_name=klass.class_name,
            teacher_key=f"selection_teacher_{idx}", teacher_name=f"选课教师{idx}",
            status="READY", weekly_hours=2, total_hours=36, start_week=1, end_week=18,
        )
        db.add(task); db.flush()
        tasks.append(task)
    if with_conflict_slots:
        for task, course in zip(tasks, (c1, c2)):
            db.add(AaScheduleItem(
                tenant_id=TID, batch_id=1, task_id=task.id, course_id=course.id,
                course_name=course.course_name, weekday=1, slot_no=1,
                start_week=1, end_week=18, week_parity="ALL", status="EFFECTIVE",
            ))
    task_ids = tuple(int(task.id) for task in tasks)
    db.commit(); db.close()
    return task_ids


def _new_batch(client, admin, name):
    resp = client.post(
        f"{BASE}/selection/batches", headers=admin,
        json={"batchName": name, "termId": str(_ensure_term())},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["batchId"]


def _make_open_batch(client, admin, course_id, capacity=5, name="2024秋选修", teaching_task_id=None):
    """正式学期建批次→加课程→发布→开选，返回 (batchId, selectionCourseId)。"""
    bid = _new_batch(client, admin, name)
    body = {"courseId": str(course_id), "capacity": capacity, "minCapacity": 1}
    if teaching_task_id is not None:
        body["teachingTaskId"] = str(teaching_task_id)
    add = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin, json=body)
    assert add.status_code == 200, add.text
    scid = add.json()["data"]["selectionCourseId"]
    publish = client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    assert publish.status_code == 200, publish.text
    opened = client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    assert opened.status_code == 200, opened.text
    return bid, scid


def test_s1_full_lifecycle(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, scid = _make_open_batch(client, admin, ids["course1"], capacity=5)
    stu = _stu_token("选甲", "SEL2401")
    r = client.get(f"{BASE}/selection/student/courses", headers=stu).json()
    assert r["code"] == 0 and any(str(c["selectionCourseId"]) == str(scid)
                                  for grp in r["data"]["items"] for c in grp["courses"])
    r = client.post(f"{BASE}/selection/student/enroll", headers=stu,
                    json={"selectionCourseId": str(scid)}).json()
    assert r["code"] == 0 and r["data"]["status"] == "SELECTED"
    my = client.get(f"{BASE}/selection/student/my", headers=stu).json()
    assert any(rec["selectionCourseId"] == str(scid) for rec in my["data"]["items"])
    cs = client.get(f"{BASE}/selection/batches/{bid}/courses", headers=admin).json()["data"]["items"]
    assert cs[0]["selectedCount"] == 1
    assert client.post(f"{BASE}/selection/student/drop", headers=stu,
                       json={"selectionCourseId": str(scid)}).json()["data"]["status"] == "DROPPED"
    assert client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin).json()["data"]["status"] == "CLOSED"
    cancelled = client.post(f"{BASE}/selection/courses/{scid}/cancel", headers=admin)
    assert cancelled.status_code == 200 and cancelled.json()["data"]["status"] == "COURSE_CANCELLED"
    locked = client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin)
    assert locked.status_code == 200 and locked.json()["data"]["status"] == "LOCKED"
    assert client.post(f"{BASE}/selection/batches/{bid}/archive", headers=admin).json()["data"]["status"] == "ARCHIVED"


def test_s2_publish_without_course_400(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, "空批次")
    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 400


def test_s3_enroll_when_not_open_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, "未开选")
    add = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                      json={"courseId": str(ids["course1"]), "capacity": 5, "minCapacity": 1})
    assert add.status_code == 200, add.text
    scid = add.json()["data"]["selectionCourseId"]
    publish = client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    assert publish.status_code == 200, publish.text
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).status_code == 409


def test_s4_capacity_full_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, scid = _make_open_batch(client, admin, ids["course1"], capacity=1)
    assert client.post(f"{BASE}/selection/student/enroll", headers=_stu_token("选甲", "SEL2401"),
                       json={"selectionCourseId": str(scid)}).json()["code"] == 0
    assert client.post(f"{BASE}/selection/student/enroll", headers=_stu_token("选乙", "SEL2402"),
                       json={"selectionCourseId": str(scid)}).status_code == 409


def test_s5_suspended_student_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, scid = _make_open_batch(client, admin, ids["course1"])
    assert client.post(f"{BASE}/selection/student/enroll", headers=_stu_token("休丙", "SEL2403"),
                       json={"selectionCourseId": str(scid)}).status_code == 403


def test_s6_duplicate_enroll_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, scid = _make_open_batch(client, admin, ids["course1"])
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).json()["code"] == 0
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).status_code == 409


def test_s7_student_cannot_manage_batch_403(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/batches", headers=stu,
                       json={"batchName": "越权", "termId": str(_ensure_term())}).status_code == 403
    assert client.get(f"{BASE}/selection/batches", headers=stu).status_code == 403


def test_s8_lock_non_closed_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, _scid = _make_open_batch(client, admin, ids["course1"])
    assert client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin).status_code == 409


def test_s9_adjust_after_lock(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    task_id, _ = _ready_tasks(ids)
    bid, scid = _make_open_batch(client, admin, ids["course1"], teaching_task_id=task_id)
    stu = _stu_token("选甲", "SEL2401")
    rid = client.post(f"{BASE}/selection/student/enroll", headers=stu,
                      json={"selectionCourseId": str(scid)}).json()["data"]["recordId"]
    assert client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin).status_code == 200
    locked = client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin)
    assert locked.status_code == 200, locked.text
    assert client.post(f"{BASE}/selection/records/{rid}/adjust", headers=admin,
                       json={"reason": "x"}).status_code == 400
    r = client.post(f"{BASE}/selection/records/{rid}/adjust", headers=admin,
                    json={"reason": "学生转专业需退课处理"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "DROPPED"


def test_s11_prereq_and_passed_block(client, db_mode):
    """稳定 courseCode 的已修拦截 + 正常课程可选。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AcademicGrade, AcademicStudent

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    db = get_sessionmaker()()
    c1 = db.query(AaCourse).filter(AaCourse.tenant_id == TID, AaCourse.course_code == "SEL001").first()
    c1.prerequisite_codes_json = '["SEL002"]'
    acad = AcademicStudent(tenant_id=TID, student_id=ids["s1"], student_no="SEL2401", name="选甲",
                           class_name="软件2401", college_name="软件学院")
    db.add(acad); db.flush()
    db.add(AcademicGrade(
        tenant_id=TID, acad_student_id=acad.id,
        course_code="SEL001", course_name="职业素养选修", credit_value=2,
        score=85, pass_status="PASSED", source="PUBLISH", record_status="ACTIVE",
    ))
    db.commit(); db.close()
    _bid, scid = _make_open_batch(client, admin, ids["course1"], name="先修批次")
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).status_code == 409
    _bid2, scid2 = _make_open_batch(client, admin, ids["course2"], name="AI批次")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid2)}).json()["code"] == 0


def test_s12_time_tick_auto_open_close(client, db_mode):
    from datetime import datetime, timedelta
    from app.db.session import get_sessionmaker
    from app.models import AaSelectionBatch

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, "定时批次")
    add = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                      json={"courseId": str(ids["course1"]), "capacity": 5, "minCapacity": 1})
    assert add.status_code == 200, add.text
    publish = client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    assert publish.status_code == 200, publish.text
    db = get_sessionmaker()()
    b = db.query(AaSelectionBatch).filter(AaSelectionBatch.id == int(bid), AaSelectionBatch.tenant_id == TID).first()
    b.select_start_at = datetime.utcnow() - timedelta(hours=1)
    db.commit(); db.close()
    r = client.post(f"{BASE}/selection/time-tick", headers=admin).json()
    assert r["code"] == 0 and r["data"]["opened"] >= 1
    assert client.get(f"{BASE}/selection/batches/{bid}", headers=admin).json()["data"]["status"] == "OPEN"


def test_s10_low_enroll_cancel_and_reselect(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, "低人数批次")
    add = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                      json={"courseId": str(ids["course1"]), "capacity": 30, "minCapacity": 2})
    assert add.status_code == 200, add.text
    scid = add.json()["data"]["selectionCourseId"]
    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin).status_code == 200
    st = client.get(f"{BASE}/selection/batches/{bid}/stats", headers=admin).json()["data"]
    assert st["lowEnrollCount"] == 1
    assert client.post(f"{BASE}/selection/courses/{scid}/cancel", headers=admin).json()["data"]["status"] == "COURSE_CANCELLED"
    guide = client.get(f"{BASE}/selection/batches/{bid}/reselect-guide", headers=admin).json()["data"]
    assert len(guide["cancelledCourses"]) == 1


def test_s13_rule_save_and_freeze_after_open(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, "规则批次")
    assert client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                       json={"courseId": str(ids["course1"]), "capacity": 5, "minCapacity": 1}).status_code == 200
    r = client.put(f"{BASE}/selection/batches/{bid}/rule", headers=admin, json={"rule": {"maxCredits": 10}})
    assert r.json()["code"] == 0 and r.json()["data"]["rule"]["maxCredits"] == 10
    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin).status_code == 200
    assert client.put(f"{BASE}/selection/batches/{bid}/rule", headers=admin,
                      json={"rule": {"maxCredits": 20}}).status_code == 409


def test_s14_reselect_flow(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, "补选批次")
    r1 = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                     json={"courseId": str(ids["course1"]), "capacity": 30, "minCapacity": 2})
    r2 = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                     json={"courseId": str(ids["course2"]), "capacity": 30, "minCapacity": 1})
    assert r1.status_code == 200 and r2.status_code == 200
    sc1 = r1.json()["data"]["selectionCourseId"]
    sc2 = r2.json()["data"]["selectionCourseId"]
    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin).status_code == 200
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(sc1)}).json()["code"] == 0
    assert client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/courses/{sc1}/cancel", headers=admin).json()["data"]["status"] == "COURSE_CANCELLED"
    guide = client.get(f"{BASE}/selection/student/reselect-guide", headers=stu).json()
    assert guide["code"] == 0
    grp = guide["data"]["items"]
    assert len(grp) == 1 and grp[0]["batch"]["batchId"] == str(bid)
    assert any(r["selectionCourseId"] == str(sc1) for r in grp[0]["cancelledRecords"])
    assert any(c["selectionCourseId"] == str(sc2) for c in grp[0]["availableCourses"])
    stu2 = _stu_token("选乙", "SEL2402")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu2,
                       json={"selectionCourseId": str(sc2), "isReselect": True}).status_code == 409
    r = client.post(f"{BASE}/selection/student/enroll", headers=stu,
                    json={"selectionCourseId": str(sc2), "isReselect": True})
    assert r.json()["code"] == 0 and r.json()["data"]["status"] == "SELECTED"


def test_s15_conflict_report(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    tt1_id, tt2_id = _ready_tasks(ids, with_conflict_slots=True)
    bid = _new_batch(client, admin, "冲突批次")
    a1 = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                     json={"courseId": str(ids["course1"]), "teachingTaskId": str(tt1_id),
                           "capacity": 30, "minCapacity": 1})
    a2 = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                     json={"courseId": str(ids["course2"]), "teachingTaskId": str(tt2_id),
                           "capacity": 30, "minCapacity": 1})
    assert a1.status_code == 200 and a2.status_code == 200
    sc1 = a1.json()["data"]["selectionCourseId"]
    sc2 = a2.json()["data"]["selectionCourseId"]
    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin).status_code == 200
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(sc1)}).json()["code"] == 0
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(sc2)}).status_code == 409
    rep = client.get(f"{BASE}/selection/batches/{bid}/conflict-report", headers=admin).json()["data"]
    assert any(s["courseName"] == "人工智能导论" and s["conflictRejectCount"] == 1 for s in rep["summary"])
    rep_hit = client.get(f"{BASE}/selection/batches/{bid}/conflict-report", headers=admin,
                         params={"studentNo": "SEL2401"}).json()["data"]
    assert len(rep_hit["items"]) == 1
    rep_miss = client.get(f"{BASE}/selection/batches/{bid}/conflict-report", headers=admin,
                          params={"studentNo": "SEL9999"}).json()["data"]
    assert len(rep_miss["items"]) == 0
    assert client.post(f"{BASE}/selection/batches/{bid}/conflict-report/export", headers=admin,
                       json={"purpose": "ab"}).status_code == 400
    exp = client.post(f"{BASE}/selection/batches/{bid}/conflict-report/export", headers=admin,
                      json={"purpose": "冲突报表测试导出"})
    assert exp.status_code == 200
    assert exp.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_s16_selection_result_merged_into_schedule(client, db_mode):
    """锁定前不并入；锁定后只并入同一课表批次，跨批次必须继续隔离。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    tt1_id, _tt2_id = _ready_tasks(ids, with_conflict_slots=True)
    bid = _new_batch(client, admin, "结果批次")
    add = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                      json={"courseId": str(ids["course1"]), "teachingTaskId": str(tt1_id),
                            "capacity": 10, "minCapacity": 1})
    assert add.status_code == 200, add.text
    sc1 = add.json()["data"]["selectionCourseId"]
    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin).status_code == 200
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(sc1)}).status_code == 200

    before_lock = client.get(f"{BASE}/schedule-batches/1/student-view", headers=admin,
                             params={"studentId": str(ids["s1"])}).json()
    assert not any(it["source"] == "ENROLLED" for it in before_lock["data"]["items"])

    assert client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin).status_code == 200
    locked = client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin)
    assert locked.status_code == 200, locked.text

    same_batch = client.get(f"{BASE}/schedule-batches/1/student-view", headers=admin,
                            params={"studentId": str(ids["s1"])}).json()
    enrolled = [it for it in same_batch["data"]["items"] if it["source"] == "ENROLLED"]
    assert len(enrolled) == 1 and enrolled[0]["courseName"] == "职业素养选修"

    cross_batch = client.get(f"{BASE}/schedule-batches/999999/student-view", headers=admin,
                             params={"studentId": str(ids["s1"])}).json()
    assert not any(it["source"] == "ENROLLED" for it in cross_batch["data"]["items"])


def test_s17_archive_list_detail_export(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, "归档批次")
    added = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                        json={"courseId": str(ids["course1"]), "capacity": 5, "minCapacity": 1})
    assert added.status_code == 200, added.text
    scid = added.json()["data"]["selectionCourseId"]
    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin).status_code == 200
    cancelled = client.post(f"{BASE}/selection/courses/{scid}/cancel", headers=admin)
    assert cancelled.status_code == 200 and cancelled.json()["data"]["status"] == "COURSE_CANCELLED"
    locked = client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin)
    assert locked.status_code == 200, locked.text
    assert client.get(f"{BASE}/selection/archive/{bid}", headers=admin).status_code == 409
    assert client.post(f"{BASE}/selection/archive/{bid}/export", headers=admin,
                       json={"purpose": "测试导出台账"}).status_code == 409
    assert client.post(f"{BASE}/selection/batches/{bid}/archive", headers=admin).json()["data"]["status"] == "ARCHIVED"
    lst = client.get(f"{BASE}/selection/archive", headers=admin).json()["data"]
    assert any(b["batchId"] == str(bid) for b in lst["items"])
    detail = client.get(f"{BASE}/selection/archive/{bid}", headers=admin).json()
    assert detail["code"] == 0 and detail["data"]["status"] == "ARCHIVED"
    assert detail["data"]["stats"]["courseCount"] == 1
    exp = client.post(f"{BASE}/selection/archive/{bid}/export", headers=admin, json={"purpose": "测试导出台账"})
    assert exp.status_code == 200
    assert client.post(f"{BASE}/selection/archive/{bid}/export", headers=admin,
                       json={"purpose": "ab"}).status_code == 400
