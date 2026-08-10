"""教学评价（/academic-affairs/evaluation/*）端点测试。

覆盖全链路：正式学期/教学任务/官方教学班名单 → 建批次 → 生成应评任务 → 发布 → 开放 →
学生匿名提交 → 关闭核算 → 发布结果 → 教师查本人结果 → 申诉/审核。
历史夹具已迁移到稳定账号绑定、真实 DB 登录和 LOCKED roster；匿名、安全与业务断言不降级。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001
_STUDENT_PASSWORD = "Test@123456"
_STUDENT_NOS = ("EV01", "EV02", "EV03", "EV04", "EV05", "EVM1", "EVM2")


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    """学生评价必须走真实数据库账号与角色上下文，禁止自行伪造 JWT。"""
    from app.services.auth_service_db import login_with_password

    data = login_with_password(student_no, _STUDENT_PASSWORD, client_type="MP")
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    """构造正式教学事实与官方 LOCKED 名单，供所有评教历史链复用。"""
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import (
        AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm,
        College, Major, Role, SchoolClass, StudentProfile, User, UserRole,
    )
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as tc_service
    from app.services import student_account_link_service as link_service

    db = get_sessionmaker()()
    term = AaTerm(
        tenant_id=TID, year_code="2024-2025", term_no=1,
        term_name="2024-2025第1学期", teaching_weeks=18,
        status="PUBLISHED", is_current=True,
    )
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(
        tenant_id=TID, major_id=major.id, class_name="软件2401",
        grade="2024", status="ACTIVE",
    )
    db.add(klass); db.flush()
    course = AaCourse(
        tenant_id=TID, course_code="EV101", course_name="高等数学",
        credit=4, status="ENABLED",
    )
    db.add(course); db.flush()
    tb = AaTeachingTaskBatch(
        tenant_id=TID, term_id=term.id, batch_name="2024秋教学任务",
        college_id=col.id, status="APPROVED",
    )
    db.add(tb); db.flush()
    tt = AaTeachingTask(
        tenant_id=TID, batch_id=tb.id,
        course_id=course.id, course_code=course.course_code, course_name=course.course_name,
        class_id=klass.id, teaching_class_name=klass.class_name,
        teacher_key="counselor01", teacher_name="王老师",
        status="READY", weekly_hours=4, total_hours=72,
        start_week=1, end_week=18,
    )
    db.add(tt); db.flush()

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

    student_ids = {}
    for idx, student_no in enumerate(_STUDENT_NOS, start=1):
        student = StudentProfile(
            tenant_id=TID, student_no=student_no, real_name=f"评教学生{idx}",
            college_id=col.id, major_id=major.id, class_id=klass.id,
            grade="2024", student_status="NORMAL", status="ACTIVE",
        )
        db.add(student); db.flush()
        user = User(
            tenant_id=TID, login_name=student_no, real_name=student.real_name,
            password_hash=hash_password(_STUDENT_PASSWORD),
            user_type="STUDENT", status="ACTIVE",
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
        student_ids[student_no] = int(student.id)

    teaching_class = tc_service.ensure_teaching_class_for_task(
        db, int(tt.id), initialize_admin_roster=True
    )
    db.flush()
    assert teaching_class.roster_status == "LOCKED"
    assert teaching_class.current_roster_version_id is not None

    ids = {
        "term": int(term.id),
        "task": int(tt.id),
        "class": int(klass.id),
        "course": int(course.id),
        "teachingClass": int(teaching_class.id),
        "students": student_ids,
    }
    db.commit(); db.close()
    return ids


def _new_batch(client, admin, ids, name):
    resp = client.post(
        f"{BASE}/evaluation/batches",
        headers=admin,
        json={
            "batchName": name,
            "termId": str(ids["term"]),
            "anonymous": True,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["batchId"]


def _generate_student_task(client, admin, bid, teaching_task_id):
    gen = client.post(
        f"{BASE}/evaluation/batches/{bid}/tasks",
        headers=admin,
        json={"teachingTaskIds": [str(teaching_task_id)], "evaluatorType": "STUDENT"},
    )
    assert gen.status_code == 200, gen.text
    payload = gen.json()
    assert payload["data"]["taskCount"] == 1
    tasks = client.get(
        f"{BASE}/evaluation/batches/{bid}/tasks",
        headers=admin,
        params={"evaluatorType": "STUDENT"},
    )
    assert tasks.status_code == 200, tasks.text
    rows = tasks.json()["data"]["items"]
    assert len(rows) == 1
    return rows[0]["taskId"]


def test_ev1_full_flow(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    create = client.post(
        f"{BASE}/evaluation/batches",
        headers=admin,
        json={
            "batchName": "2024秋评教",
            "termId": str(ids["term"]),
            "anonymous": True,
            "template": {"items": [{"q": "教学态度", "type": "scale5"}]},
        },
    )
    assert create.status_code == 200, create.text
    bid = create.json()["data"]["batchId"]
    tid_ = _generate_student_task(client, admin, bid, ids["task"])

    publish = client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin)
    assert publish.status_code == 200, publish.text
    opened = client.post(f"{BASE}/evaluation/batches/{bid}/open", headers=admin)
    assert opened.status_code == 200 and opened.json()["data"]["status"] == "OPEN"

    for sn, sc in (("EV01", 90), ("EV02", 80)):
        r = client.post(
            f"{BASE}/evaluation/submit",
            headers=_stu_token("学生", sn),
            json={
                "taskId": tid_,
                "objectiveScore": sc,
                "answers": {"教学态度": 5},
                "comment": "很好",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["code"] == 0

    close = client.post(f"{BASE}/evaluation/batches/{bid}/close-score", headers=admin)
    assert close.status_code == 200 and close.json()["data"]["status"] == "RESULT_READY"
    pub = client.post(f"{BASE}/evaluation/batches/{bid}/publish-results", headers=admin)
    assert pub.status_code == 200, pub.text
    results = client.get(f"{BASE}/evaluation/batches/{bid}/results", headers=admin).json()["data"]["items"]
    assert len(results) == 1
    assert results[0]["studentAvg"] == 85.0
    assert results[0]["level"] == "GOOD"
    assert results[0]["studentCount"] == 2

    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationRecord

    db = get_sessionmaker()()
    recs = db.query(AaEvaluationRecord).filter(
        AaEvaluationRecord.tenant_id == TID,
        AaEvaluationRecord.evaluator_type == "STUDENT",
    ).all()
    assert len(recs) == 2
    assert all(not hasattr(r, "evaluator_key") or getattr(r, "evaluator_key", None) is None for r in recs)
    assert all("EV01" not in (r.answers_json or "") and "EV02" not in (r.answers_json or "") for r in recs)
    db.close()

    my = client.get(
        f"{BASE}/evaluation/batches/{bid}/my-results",
        headers=_hdr(client, "counselor01"),
    ).json()["data"]["items"]
    assert any(x["level"] == "GOOD" for x in my)
    archived = client.post(f"{BASE}/evaluation/batches/{bid}/archive", headers=admin)
    assert archived.status_code == 200 and archived.json()["data"]["status"] == "ARCHIVED"


def test_ev_multisource_composite(client, db_mode):
    """学生均分 + 督导评价按当前权重合成综合分。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, ids, "多来源评教")
    stu_task = _generate_student_task(client, admin, bid, ids["task"])
    g2 = client.post(
        f"{BASE}/evaluation/batches/{bid}/role-tasks",
        headers=admin,
        json={
            "evaluatorType": "SUPERVISOR",
            "assignments": [
                {"teachingTaskId": str(ids["task"]), "evaluatorKey": "school_admin01"}
            ],
        },
    )
    assert g2.status_code == 200 and g2.json()["data"]["taskCount"] == 1
    assert client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/evaluation/batches/{bid}/open", headers=admin).status_code == 200
    sup_rows = client.get(
        f"{BASE}/evaluation/batches/{bid}/tasks",
        headers=admin,
        params={"evaluatorType": "SUPERVISOR"},
    ).json()["data"]["items"]
    sup_task = sup_rows[0]["taskId"]

    for sn, sc in (("EVM1", 90), ("EVM2", 80)):
        resp = client.post(
            f"{BASE}/evaluation/submit",
            headers=_stu_token("学生", sn),
            json={"taskId": stu_task, "objectiveScore": sc, "answers": {"x": 5}},
        )
        assert resp.status_code == 200, resp.text

    sup_resp = client.post(
        f"{BASE}/evaluation/submit",
        headers=admin,
        json={"taskId": sup_task, "objectiveScore": 95, "answers": {"x": 5}},
    )
    assert sup_resp.status_code == 200 and sup_resp.json()["code"] == 0
    assert client.post(f"{BASE}/evaluation/batches/{bid}/close-score", headers=admin).status_code == 200
    r = client.get(f"{BASE}/evaluation/batches/{bid}/results", headers=admin).json()["data"]["items"][0]
    assert r["studentAvg"] == 85.0
    assert r["supervisorAvg"] == 95.0
    assert r["studentCount"] == 2
    assert r["compositeScore"] == 87.5 and r["level"] == "GOOD"


def test_ev2_publish_without_task_400(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, ids, "空评教")
    assert client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin).status_code == 400


def test_ev3_submit_not_open_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, ids, "未开放")
    tid_ = _generate_student_task(client, admin, bid, ids["task"])
    publish = client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin)
    assert publish.status_code == 200, publish.text
    resp = client.post(
        f"{BASE}/evaluation/submit",
        headers=_stu_token("学生", "EV03"),
        json={"taskId": tid_, "objectiveScore": 88},
    )
    assert resp.status_code == 409


def test_ev4_appeal_flow(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _new_batch(client, admin, ids, "申诉评教")
    tid_ = _generate_student_task(client, admin, bid, ids["task"])
    assert client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/evaluation/batches/{bid}/open", headers=admin).status_code == 200
    submit = client.post(
        f"{BASE}/evaluation/submit",
        headers=_stu_token("学生", "EV04"),
        json={"taskId": tid_, "objectiveScore": 55},
    )
    assert submit.status_code == 200, submit.text
    assert client.post(f"{BASE}/evaluation/batches/{bid}/close-score", headers=admin).status_code == 200
    assert client.post(f"{BASE}/evaluation/batches/{bid}/publish-results", headers=admin).status_code == 200
    rid = client.get(f"{BASE}/evaluation/batches/{bid}/results", headers=admin).json()["data"]["items"][0]["resultId"]

    teacher = _hdr(client, "counselor01")
    assert client.post(
        f"{BASE}/evaluation/appeals",
        headers=teacher,
        json={"resultId": rid, "reason": "x"},
    ).status_code == 400
    appeal = client.post(
        f"{BASE}/evaluation/appeals",
        headers=teacher,
        json={"resultId": rid, "reason": "评分异常，学生恶意打分"},
    )
    assert appeal.status_code == 200, appeal.text
    aid = appeal.json()["data"]["appealId"]
    reviewed = client.post(
        f"{BASE}/evaluation/appeals/{aid}/review",
        headers=admin,
        json={"action": "RESOLVE"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["status"] == "RESOLVED"


def test_ev5_student_cannot_manage_403(client, db_mode):
    ids = _seed(db_mode)
    stu = _stu_token("学生", "EV05")
    resp = client.post(
        f"{BASE}/evaluation/batches",
        headers=stu,
        json={"batchName": "越权", "termId": str(ids["term"]), "anonymous": True},
    )
    assert resp.status_code == 403
