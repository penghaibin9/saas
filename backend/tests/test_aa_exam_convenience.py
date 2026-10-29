"""D7-U 考务便利性与批量查询合同（MySQL-only）。"""
import pytest
from sqlalchemy import event

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm, College, Major, SchoolClass

    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2097-2098", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    college = College(tenant_id=TID, college_name="D7软件学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="D7软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="D7软件9701", grade="2097", status="ACTIVE")
    db.add(klass); db.flush()
    task_batch = AaTeachingTaskBatch(
        tenant_id=TID,
        term_id=term.id,
        batch_name="D7正式教学任务",
        college_id=college.id,
        status="APPROVED",
    )
    db.add(task_batch); db.flush()
    task_ids = []
    for idx in range(3):
        course = AaCourse(
            tenant_id=TID,
            course_code=f"D7U{idx + 1}",
            course_name=f"D7课程{idx + 1}",
            credit=2,
            version=1,
            status="ENABLED",
        )
        db.add(course); db.flush()
        task = AaTeachingTask(
            tenant_id=TID,
            batch_id=task_batch.id,
            course_id=course.id,
            course_name=course.course_name,
            class_id=klass.id,
            teaching_class_name=klass.class_name,
            teacher_key=f"d7_teacher_{idx + 1}",
            teacher_name=f"D7教师{idx + 1}",
            status="READY",
        )
        db.add(task); db.flush()
        task_ids.append(int(task.id))
    result = {"term": int(term.id), "tasks": task_ids}
    db.commit(); db.close()
    return result


def _create_batch(client, auth_headers, term_id):
    response = client.post(
        f"{BASE}/exam/batches",
        headers=auth_headers,
        json={"batchName": "D7-U期末考试", "termId": str(term_id)},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["data"]["batchId"])


def _preview(client, auth_headers, bid, task_ids):
    response = client.post(
        f"{BASE}/exam/batches/{bid}/course-candidates/preview",
        headers=auth_headers,
        json={"teachingTaskIds": task_ids},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _confirm(client, auth_headers, bid, preview_token):
    return client.post(
        f"{BASE}/exam/batches/{bid}/course-candidates/confirm",
        headers=auth_headers,
        json={"previewToken": preview_token},
    )


def test_d7_u_candidates_preview_confirm_and_readiness(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaExamCourse

    ids = _seed(db_mode)
    bid = _create_batch(client, auth_headers, ids["term"])

    readiness = client.get(f"{BASE}/exam/batches/{bid}/readiness", headers=auth_headers)
    assert readiness.status_code == 200, readiness.text
    summary = readiness.json()["data"]
    assert summary["eligibleCourseCount"] == 3
    assert summary["pendingCandidateCount"] == 3
    assert summary["canPublish"] is False

    candidates = client.get(
        f"{BASE}/exam/batches/{bid}/course-candidates?pageSize=2",
        headers=auth_headers,
    )
    assert candidates.status_code == 200, candidates.text
    data = candidates.json()["data"]
    assert data["total"] == 3
    assert len(data["items"]) == 2

    payload = _preview(client, auth_headers, bid, ids["tasks"][:2])
    assert payload["ready"] == 2
    assert payload["blocked"] == 0
    assert payload["previewToken"]

    db = get_sessionmaker()()
    assert db.query(AaExamCourse).filter(
        AaExamCourse.tenant_id == TID,
        AaExamCourse.batch_id == bid,
    ).count() == 0
    db.close()

    confirmed = _confirm(client, auth_headers, bid, payload["previewToken"])
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["succeeded"] == 2

    db = get_sessionmaker()()
    rows = db.query(AaExamCourse).filter(
        AaExamCourse.tenant_id == TID,
        AaExamCourse.batch_id == bid,
    ).all()
    assert len(rows) == 2
    assert {row.status for row in rows} == {"PENDING_CONFIRM"}
    db.close()

    stale = _confirm(client, auth_headers, bid, payload["previewToken"])
    assert stale.status_code == 409

    after = client.get(f"{BASE}/exam/batches/{bid}/readiness", headers=auth_headers).json()["data"]
    assert after["circledCourseCount"] == 2
    assert after["pendingCandidateCount"] == 1
    assert after["canPublish"] is False
    assert not any("尚未圈定" in reason for reason in after["blockingReasons"])
    assert any("待学院确认" in reason for reason in after["blockingReasons"])


@pytest.mark.parametrize("status", ["PUBLISHED", "FINISHED", "ARCHIVED"])
def test_post_publish_readiness_keeps_source_and_roster_defects(client, auth_headers, db_mode, monkeypatch, status):
    from app.db.session import get_sessionmaker
    from app.models import AaExamBatch, AaExamCourse, AaTeachingTaskBatch

    ids = _seed(db_mode)
    bid = _create_batch(client, auth_headers, ids["term"])
    preview = _preview(client, auth_headers, bid, ids["tasks"][:1])
    assert _confirm(client, auth_headers, bid, preview["previewToken"]).status_code == 200
    with get_sessionmaker()() as db:
        batch = db.get(AaExamBatch, bid)
        batch.status = status
        course = db.query(AaExamCourse).filter_by(tenant_id=TID, batch_id=bid).one()
        course.status = "CONFIRMED"
        # A legacy published record can lack both resources and offering ownership.
        db.query(AaTeachingTaskBatch).filter_by(tenant_id=TID, term_id=ids["term"]).one().college_id = None
        db.commit()

    response = client.get(f"{BASE}/exam/batches/{bid}/readiness", headers=auth_headers)
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["batchStatus"] == status
    assert result["canPublish"] is False
    assert result["roomShortageCount"] == 1
    assert not any("尚未进入可发布阶段" in reason for reason in result["blockingReasons"])
    assert any("缺少有效课程或开课责任单位" in reason for reason in result["blockingReasons"])
    assert any("名单" in reason for reason in result["blockingReasons"])

    from app.models import AaExamInvigilator, AaExamRoom
    with get_sessionmaker()() as db:
        course = db.query(AaExamCourse).filter_by(tenant_id=TID, batch_id=bid).one()
        cid = course.id
        room = AaExamRoom(tenant_id=TID, exam_course_id=cid, room_seq=1, classroom_text="历史虚构考场", capacity=30, planned_count=1)
        db.add(room); db.flush()
        rid = room.id
        db.add(AaExamInvigilator(tenant_id=TID, exam_room_id=rid, teacher_key="legacy_invigilator", teacher_name="历史虚构监考", role="CHIEF", confirm_status="ASSIGNED"))
        db.commit()
    path = f"{BASE}/exam/courses/{cid}/rooms"
    rooms = client.get(path, headers=auth_headers)
    assert rooms.status_code == 200, rooms.text
    assert rooms.json()["data"]["items"][0]["capacity"] == 30
    invigilator_path = f"{BASE}/exam/rooms/{rid}/invigilators"
    invigilators = client.get(invigilator_path, headers=auth_headers)
    assert invigilators.status_code == 200, invigilators.text
    assert [item["teacherKey"] for item in invigilators.json()["data"]["items"]] == ["legacy_invigilator"]
    assert client.post(path, headers=auth_headers, json={"classroomText":"不可补造", "capacity":50}).status_code == 409
    assert client.post(invigilator_path, headers=auth_headers, json={"teacherKey":"not_allowed", "teacherName":"不可补造", "role":"ASSISTANT"}).status_code == 409
    with get_sessionmaker()() as db:
        db.get(AaExamBatch, bid).status = "COURSE_CONFIRMED"
        db.commit()
    assert client.get(path, headers=auth_headers).status_code == 409
    assert client.get(invigilator_path, headers=auth_headers).status_code == 409
    with get_sessionmaker()() as db:
        db.get(AaExamBatch, bid).status = status
        db.commit()
    from types import SimpleNamespace
    from app.modules.academic_affairs.services import academic_affairs_exam_facade
    monkeypatch.setattr(academic_affairs_exam_facade._legacy, "_ctx", lambda *_args: SimpleNamespace(scope_type="COLLEGE", college_ids=set()))
    assert client.get(path, headers=auth_headers).status_code == 409
    assert client.get(invigilator_path, headers=auth_headers).status_code == 409


def test_d7_u_course_list_batches_roster_snapshot_query(client, auth_headers, db_mode):
    from app.db.session import get_engine
    from app.modules.academic_affairs.routers import academic_affairs_bundle

    ids = _seed(db_mode)
    bid = _create_batch(client, auth_headers, ids["term"])
    payload = _preview(client, auth_headers, bid, ids["tasks"])
    confirmed = _confirm(client, auth_headers, bid, payload["previewToken"])
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["succeeded"] == 3

    owner = None
    for route in academic_affairs_bundle.build_router().routes:
        if (
            getattr(route, "path", "") == "/academic-affairs/exam/batches/{bid}/courses"
            and "GET" in (getattr(route, "methods", set()) or set())
        ):
            owner = route.endpoint.__module__
            break
    assert owner == "app.modules.academic_affairs.routers.exam_core_router"

    statements = []
    engine = get_engine()

    def _capture(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT") and "t_aa_roster_consumer_snapshot" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _capture)
    try:
        response = client.get(
            f"{BASE}/exam/batches/{bid}/courses?pageSize=100",
            headers=auth_headers,
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == 3
    assert len(statements) == 1, f"roster snapshot SELECT count={len(statements)}"
