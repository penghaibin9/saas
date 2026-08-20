"""选课多轮次+抽签（/academic-affairs/selection/**/rounds*）端点测试。

覆盖重点：
- 轮次生命周期（建→开→关→摇号 DRAWN 终态）；同批次双 OPEN 409
- 抽签轮：志愿登记不占容量；超额摇号后 中签=容量数、未中签 LOTTERY_LOST；绝不超容
- 摇号确定性（同输入重跑同结果——通过“摇号只许一次”的 409 终态保证不可重摇）
- 三态选课控制：allow_enroll=False 拦选课；allow_drop=False 拦退课
- 抽签志愿可撤回（不动容量）
- 学生越权操作轮次 403

历史夹具已对齐正式 termId、真实 User/Role/StudentAccountLink 与 DB 登录上下文；
轮次、容量、摇号与越权业务断言保持原强度。MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001
_PASSWORD = "Test@123456"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.services.auth_service_db import login_with_password

    data = login_with_password(student_no, _PASSWORD, client_type="MP")
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _ensure_term():
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
        if term is None:
            term = AaTerm(
                tenant_id=TID,
                year_code="2024-2025",
                term_no=1,
                term_name="2024-2025第1学期",
                teaching_weeks=18,
                status="PUBLISHED",
                is_current=True,
            )
            db.add(term)
            db.flush()
        else:
            term.teaching_weeks = 18
            term.status = "PUBLISHED"
            term.is_current = True
        term_id = int(term.id)
        db.commit()
        return term_id
    finally:
        db.close()


def _seed(db_mode, students=3):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, College, Major, Role, SchoolClass, StudentProfile, User, UserRole
    from app.services import student_account_link_service as link_service

    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(
        tenant_id=TID, major_id=major.id, class_name="软件2401",
        grade="2024", status="ACTIVE",
    )
    db.add(klass); db.flush()
    c1 = AaCourse(
        tenant_id=TID, course_code="RND001", course_name="轮次选修课",
        credit=2, status="ENABLED",
    )
    db.add(c1); db.flush()

    student_role = db.query(Role).filter(
        Role.tenant_id == TID,
        Role.role_code == "STUDENT",
        Role.is_deleted.is_(False),
    ).first()
    if student_role is None:
        student_role = Role(
            tenant_id=TID, role_code="STUDENT", role_name="学生", status="ACTIVE"
        )
        db.add(student_role); db.flush()
    else:
        student_role.status = "ACTIVE"

    stus = []
    for i in range(students):
        student_no = f"RND24{i + 1:02d}"
        student = StudentProfile(
            tenant_id=TID, student_no=student_no, real_name=f"轮学{i + 1}",
            college_id=col.id, major_id=major.id, class_id=klass.id, grade="2024",
            student_status="NORMAL", status="ACTIVE",
        )
        db.add(student); db.flush()
        user = User(
            tenant_id=TID, login_name=student_no, real_name=student.real_name,
            password_hash=hash_password(_PASSWORD), user_type="STUDENT", status="ACTIVE",
        )
        db.add(user); db.flush()
        db.add(UserRole(
            tenant_id=TID, user_id=int(user.id), role_id=int(student_role.id), status="ACTIVE"
        ))
        link_service.bind_in_session(
            db,
            tenant_id=TID,
            student_id=int(student.id),
            user_id=int(user.id),
            source="TEST_FIXTURE",
            login_name=student_no,
            student_no=student_no,
        )
        stus.append(student_no)
    course_id = int(c1.id)
    db.commit(); db.close()
    return {"course1": course_id, "studentNos": stus}


def _ready_teaching_task(term_id, course_id):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaProgramCourse, AaTeachingTask, AaTeachingTaskBatch

    db = get_sessionmaker()()
    try:
        course = db.query(AaCourse).filter(
            AaCourse.tenant_id == TID,
            AaCourse.id == int(course_id),
            AaCourse.is_deleted.is_(False),
        ).one()
        task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=int(term_id),
            college_id=None,
            batch_name=f"轮次测试教学任务-{course.id}",
            status="APPROVED",
        )
        db.add(task_batch); db.flush()
        source = AaProgramCourse(
            tenant_id=TID,
            program_id=881000 + int(course.id),
            course_id=course.id,
            course_name=course.course_name,
            open_term_no=1,
            module="MAJOR_CORE",
            credit_snapshot=course.credit,
            formation_mode="SELECTABLE",
        )
        db.add(source); db.flush()
        task = AaTeachingTask(
            tenant_id=TID,
            batch_id=task_batch.id,
            course_id=course.id,
            course_code=course.course_code,
            course_name=course.course_name,
            teacher_key=f"ROUND-T-{course.id}",
            teacher_name="轮次测试教师",
            source_program_course_id=source.id,
            formation_mode="SELECTABLE",
            status="READY",
            weekly_hours=2,
            total_hours=36,
            start_week=1,
            end_week=18,
        )
        db.add(task); db.flush()
        task_id = task.id
        db.commit()
        return task_id
    finally:
        db.close()


def _open_batch(client, admin, course_id, capacity=5):
    term_id = _ensure_term()
    teaching_task_id = _ready_teaching_task(term_id, course_id)
    create = client.post(
        f"{BASE}/selection/batches",
        headers=admin,
        json={"batchName": "轮次测试批次", "termId": str(term_id)},
    )
    assert create.status_code == 200, create.text
    bid = create.json()["data"]["batchId"]
    added = client.post(
        f"{BASE}/selection/batches/{bid}/courses",
        headers=admin,
        json={
            "courseId": str(course_id),
            "teachingTaskId": str(teaching_task_id),
            "capacity": capacity,
            "minCapacity": 1,
        },
    )
    assert added.status_code == 200, added.text
    scid = added.json()["data"]["selectionCourseId"]
    published = client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    assert published.status_code == 200, published.text
    opened = client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    assert opened.status_code == 200, opened.text
    return bid, scid


def _add_round(client, admin, bid, name="第一轮预选", mode="LOTTERY", **kw):
    body = {"roundName": name, "mode": mode, **kw}
    r = client.post(f"{BASE}/selection/batches/{bid}/rounds", headers=admin, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]["roundId"]


def _course_state(client, admin, bid, scid):
    items = client.get(f"{BASE}/selection/batches/{bid}/courses", headers=admin).json()["data"]["items"]
    return next(c for c in items if str(c["selectionCourseId"]) == str(scid))


def test_round_lifecycle_and_single_open(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, _scid = _open_batch(client, admin, ids["course1"])
    r1 = _add_round(client, admin, bid, "第一轮预选", "LOTTERY")
    r2 = _add_round(client, admin, bid, "第二轮正选", "FCFS")
    assert client.post(f"{BASE}/selection/rounds/{r1}/open", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/rounds/{r2}/open", headers=admin).status_code == 409
    assert client.post(f"{BASE}/selection/rounds/{r1}/close", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/rounds/{r2}/open", headers=admin).status_code == 200


def test_lottery_register_does_not_consume_capacity(client, db_mode):
    ids = _seed(db_mode, students=2)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"], capacity=5)
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    assert client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin).status_code == 200
    for i, sno in enumerate(ids["studentNos"][:2]):
        r = client.post(
            f"{BASE}/selection/student/enroll",
            headers=_stu_token(f"轮学{i + 1}", sno),
            json={"selectionCourseId": str(scid)},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "PENDING_LOTTERY"
    assert _course_state(client, admin, bid, scid)["selectedCount"] == 0


def test_lottery_draw_respects_capacity(client, db_mode):
    ids = _seed(db_mode, students=3)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"], capacity=1)
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    assert client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin).status_code == 200
    for i, sno in enumerate(ids["studentNos"]):
        r = client.post(
            f"{BASE}/selection/student/enroll",
            headers=_stu_token(f"轮学{i + 1}", sno),
            json={"selectionCourseId": str(scid)},
        )
        assert r.status_code == 200, r.text
    assert client.post(f"{BASE}/selection/rounds/{rid}/close", headers=admin).status_code == 200
    d = client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=admin)
    assert d.status_code == 200, d.text
    res = d.json()["data"]
    assert res["totalWinners"] == 1 and res["totalLosers"] == 2
    assert _course_state(client, admin, bid, scid)["selectedCount"] == 1

    from app.db.session import get_sessionmaker
    from app.models import AaSelectionRecord

    db = get_sessionmaker()()
    rows = db.query(AaSelectionRecord).filter(AaSelectionRecord.batch_id == int(bid)).all()
    statuses = sorted(r.status for r in rows)
    db.close()
    assert statuses == ["LOTTERY_LOST", "LOTTERY_LOST", "SELECTED"]


def test_lottery_all_win_when_under_capacity(client, db_mode):
    ids = _seed(db_mode, students=2)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"], capacity=5)
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    assert client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin).status_code == 200
    for i, sno in enumerate(ids["studentNos"][:2]):
        r = client.post(
            f"{BASE}/selection/student/enroll",
            headers=_stu_token(f"轮学{i + 1}", sno),
            json={"selectionCourseId": str(scid)},
        )
        assert r.status_code == 200, r.text
    assert client.post(f"{BASE}/selection/rounds/{rid}/close", headers=admin).status_code == 200
    drawn = client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=admin)
    assert drawn.status_code == 200, drawn.text
    res = drawn.json()["data"]
    assert res["totalWinners"] == 2 and res["totalLosers"] == 0
    assert _course_state(client, admin, bid, scid)["selectedCount"] == 2


def test_draw_gates(client, db_mode):
    ids = _seed(db_mode, students=1)
    admin = _hdr(client, "school_admin01")
    bid, _scid = _open_batch(client, admin, ids["course1"])
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    assert client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=admin).status_code == 409
    assert client.post(f"{BASE}/selection/rounds/{rid}/close", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=admin).status_code == 409


def test_enroll_blocked_when_round_disallows(client, db_mode):
    ids = _seed(db_mode, students=1)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"])
    rid = _add_round(client, admin, bid, "补退选(只可退)", "FCFS", allowEnroll=False)
    assert client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin).status_code == 200
    r = client.post(
        f"{BASE}/selection/student/enroll",
        headers=_stu_token("轮学1", ids["studentNos"][0]),
        json={"selectionCourseId": str(scid)},
    )
    assert r.status_code == 409, r.text


def test_drop_blocked_when_round_disallows(client, db_mode):
    ids = _seed(db_mode, students=1)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"])
    stu = _stu_token("轮学1", ids["studentNos"][0])
    assert client.post(
        f"{BASE}/selection/student/enroll",
        headers=stu,
        json={"selectionCourseId": str(scid)},
    ).status_code == 200
    rid = _add_round(client, admin, bid, "正选(只可选)", "FCFS", allowDrop=False)
    assert client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin).status_code == 200
    r = client.post(
        f"{BASE}/selection/student/drop",
        headers=stu,
        json={"selectionCourseId": str(scid)},
    )
    assert r.status_code == 409, r.text


def test_withdraw_pending_lottery(client, db_mode):
    ids = _seed(db_mode, students=1)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"], capacity=5)
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    assert client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin).status_code == 200
    stu = _stu_token("轮学1", ids["studentNos"][0])
    enroll = client.post(
        f"{BASE}/selection/student/enroll", headers=stu,
        json={"selectionCourseId": str(scid)},
    )
    assert enroll.status_code == 200, enroll.text
    r = client.post(
        f"{BASE}/selection/student/drop", headers=stu,
        json={"selectionCourseId": str(scid)},
    )
    assert r.status_code == 200 and r.json()["data"]["status"] == "DROPPED"
    assert _course_state(client, admin, bid, scid)["selectedCount"] == 0


def test_student_cannot_manage_rounds(client, db_mode):
    ids = _seed(db_mode, students=1)
    admin = _hdr(client, "school_admin01")
    bid, _scid = _open_batch(client, admin, ids["course1"])
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    stu = _stu_token("轮学1", ids["studentNos"][0])
    assert client.post(
        f"{BASE}/selection/batches/{bid}/rounds", headers=stu,
        json={"roundName": "越权轮"},
    ).status_code == 403
    assert client.post(f"{BASE}/selection/rounds/{rid}/open", headers=stu).status_code == 403
    assert client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=stu).status_code == 403
