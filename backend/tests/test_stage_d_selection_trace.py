"""Stage D selection DecisionTrace integration on the formal student endpoint."""
from __future__ import annotations

from datetime import datetime, timedelta

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _admin(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _student_token(student_no: str, name: str):
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": f"stage-d-{student_no}",
        "realName": name,
        "studentNo": student_no,
        "userType": "STUDENT",
        "tid": "demo-school",
        "tenantId": str(TID),
        "activeContextId": "ctx_student_self",
        "currentRoleCode": "STUDENT",
        "clientType": "MP",
    })
    return {"Authorization": f"Bearer {token}"}


def _seed(db_mode, *, student_count=2):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTerm, College, Major, SchoolClass, StudentProfile

    db = get_sessionmaker()()
    try:
        college = College(tenant_id=TID, college_name="D1学院", status="ACTIVE")
        db.add(college); db.flush()
        major = Major(tenant_id=TID, college_id=college.id, major_name="D1专业", status="ACTIVE")
        db.add(major); db.flush()
        klass = SchoolClass(
            tenant_id=TID,
            major_id=major.id,
            class_name="D1-2401",
            grade="2024",
            status="ACTIVE",
            class_status="NORMAL",
        )
        db.add(klass); db.flush()
        term = AaTerm(
            tenant_id=TID,
            year_code="2026-2027",
            term_no=1,
            term_name="2026-2027-1",
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow() + timedelta(days=120),
            status="PUBLISHED",
            is_current=True,
        )
        course = AaCourse(
            tenant_id=TID,
            course_code="DTRACE101",
            course_name="DecisionTrace选修课",
            credit=2,
            status="ENABLED",
        )
        db.add_all([term, course]); db.flush()
        students = []
        for index in range(student_count):
            student = StudentProfile(
                tenant_id=TID,
                student_no=f"DTR24{index + 1:02d}",
                real_name=f"DTrace学生{index + 1}",
                college_id=college.id,
                major_id=major.id,
                class_id=klass.id,
                grade="2024",
                student_status="NORMAL",
                status="ACTIVE",
            )
            db.add(student); db.flush()
            students.append((student.student_no, student.real_name))
        result = {"termId": term.id, "courseId": course.id, "students": students}
        db.commit()
        return result
    finally:
        db.close()


def _ready_teaching_task(term_id, course_id):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch

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
            batch_name=f"Stage D教学任务-{course.id}",
            status="APPROVED",
        )
        db.add(task_batch); db.flush()
        task = AaTeachingTask(
            tenant_id=TID,
            batch_id=task_batch.id,
            course_id=course.id,
            course_code=course.course_code,
            course_name=course.course_name,
            teacher_key=f"DTRACE-T-{course.id}",
            teacher_name="DecisionTrace测试教师",
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


def _open_batch(client, admin, ids, *, capacity):
    teaching_task_id = _ready_teaching_task(ids["termId"], ids["courseId"])
    created = client.post(
        f"{BASE}/selection/batches",
        headers=admin,
        json={"batchName": "Stage D DecisionTrace", "termId": str(ids["termId"])},
    )
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["batchId"]
    added = client.post(
        f"{BASE}/selection/batches/{bid}/courses",
        headers=admin,
        json={
            "courseId": str(ids["courseId"]),
            "teachingTaskId": str(teaching_task_id),
            "capacity": capacity,
            "minCapacity": 0,
        },
    )
    assert added.status_code == 200, added.text
    scid = added.json()["data"]["selectionCourseId"]
    published = client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    assert published.status_code == 200, published.text
    opened = client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    assert opened.status_code == 200, opened.text
    return bid, scid


def _assert_safe_trace(body, rule_code):
    assert body["code"] == 409001
    assert body["message"]
    trace = body["decisionTrace"]
    assert trace["schemaVersion"] == "1.0"
    assert trace["domain"] == "SELECTION"
    assert trace["action"] == "ENROLL"
    assert trace["decision"] == "DENIED"
    assert trace["ruleCode"] == rule_code
    assert trace["subject"]["studentId"].startswith("masked:")
    assert "tenantId" not in str(trace)
    assert "permission" not in str(trace).lower()
    assert "sql" not in str(trace).lower()
    assert trace["target"]["courseCode"] == "DTRACE101"


def test_closed_batch_returns_batch_not_open_decision_trace(client, db_mode):
    ids = _seed(db_mode, student_count=1)
    admin = _admin(client)
    bid, scid = _open_batch(client, admin, ids, capacity=2)
    closed = client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin)
    assert closed.status_code == 200, closed.text

    sno, name = ids["students"][0]
    response = client.post(
        f"{BASE}/selection/student/enroll",
        headers=_student_token(sno, name),
        json={"selectionCourseId": str(scid)},
    )
    assert response.status_code == 409, response.text
    _assert_safe_trace(response.json(), "BATCH_NOT_OPEN")
    assert response.json()["decisionTrace"]["availableResolutions"][0]["code"] == "RETRY_DURING_OPEN_WINDOW"


def test_full_course_returns_course_full_decision_trace(client, db_mode):
    ids = _seed(db_mode, student_count=2)
    admin = _admin(client)
    _bid, scid = _open_batch(client, admin, ids, capacity=1)

    first_no, first_name = ids["students"][0]
    first = client.post(
        f"{BASE}/selection/student/enroll",
        headers=_student_token(first_no, first_name),
        json={"selectionCourseId": str(scid)},
    )
    assert first.status_code == 200, first.text

    second_no, second_name = ids["students"][1]
    second = client.post(
        f"{BASE}/selection/student/enroll",
        headers=_student_token(second_no, second_name),
        json={"selectionCourseId": str(scid)},
    )
    assert second.status_code == 409, second.text
    _assert_safe_trace(second.json(), "COURSE_FULL")
    assert second.json()["decisionTrace"]["availableResolutions"][0]["code"] == "CHOOSE_AVAILABLE_COURSE"
