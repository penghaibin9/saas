"""B-W4 · SelectionCourse must be bound to one legal current TeachingTask.

Focused MySQL contracts only.  The task-identity surface stays runnable on the
standalone B subseal, while an INT-overlay run seeds the canonical direct
ProgramCourse provenance required by the shared formation runtime.
"""
from __future__ import annotations

import itertools
from pathlib import Path

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001
_SEQ = itertools.count(1)
_ROOT = Path(__file__).resolve().parents[1]


def _admin(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaCourse,
        AaProgramCourse,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        College,
        Major,
        SchoolClass,
    )

    n = next(_SEQ)
    db = get_sessionmaker()()
    try:
        college = College(tenant_id=TID, college_name=f"W4学院{n}", status="ACTIVE")
        db.add(college); db.flush()
        major = Major(
            tenant_id=TID,
            college_id=college.id,
            major_name=f"W4专业{n}",
            status="ACTIVE",
        )
        db.add(major); db.flush()
        klass = SchoolClass(
            tenant_id=TID,
            major_id=major.id,
            class_name=f"W4-{n:02d}01",
            grade="2097",
            status="ACTIVE",
        )
        db.add(klass); db.flush()

        term = AaTerm(
            tenant_id=TID,
            year_code=f"21{n:02d}-21{n + 1:02d}",
            term_no=1,
            term_name=f"W4同学期{n}",
            teaching_weeks=20,
            status="PUBLISHED",
            is_current=False,
        )
        other_term = AaTerm(
            tenant_id=TID,
            year_code=f"22{n:02d}-22{n + 1:02d}",
            term_no=1,
            term_name=f"W4异学期{n}",
            teaching_weeks=20,
            status="PUBLISHED",
            is_current=False,
        )
        db.add_all([term, other_term]); db.flush()

        course = AaCourse(
            tenant_id=TID,
            course_code=f"W4A{n:04d}",
            course_name=f"W4正式课程{n}",
            credit=2,
            status="ENABLED",
        )
        other_course = AaCourse(
            tenant_id=TID,
            course_code=f"W4B{n:04d}",
            course_name=f"W4其它课程{n}",
            credit=2,
            status="ENABLED",
        )
        db.add_all([course, other_course]); db.flush()

        # The standalone B subseal predates the INT-owned provenance columns.  When
        # those columns are present in an ephemeral INT merge, seed the exact direct
        # source relation instead of weakening or mocking the production guard.
        formation_source = None
        if (
            hasattr(AaTeachingTask, "source_program_course_id")
            and hasattr(AaTeachingTask, "formation_mode")
            and hasattr(AaProgramCourse, "formation_mode")
        ):
            formation_source = AaProgramCourse(
                tenant_id=TID,
                program_id=880000 + n,
                course_id=course.id,
                course_name=course.course_name,
                open_term_no=1,
                module="MAJOR_CORE",
                credit_snapshot=2,
                formation_mode="SELECTABLE",
            )
            db.add(formation_source); db.flush()

        task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            college_id=college.id,
            batch_name=f"W4任务批次{n}",
            status="APPROVED",
        )
        other_task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=other_term.id,
            college_id=college.id,
            batch_name=f"W4异学期任务批次{n}",
            status="APPROVED",
        )
        db.add_all([task_batch, other_task_batch]); db.flush()

        def task(batch, bound_course, status, suffix):
            row = AaTeachingTask(
                tenant_id=TID,
                batch_id=batch.id,
                course_id=bound_course.id,
                course_code=bound_course.course_code,
                course_name=bound_course.course_name,
                class_id=klass.id,
                teaching_class_name=klass.class_name,
                teacher_key=f"w4_teacher_{n}_{suffix}",
                teacher_name=f"W4教师{n}-{suffix}",
                weekly_hours=2,
                total_hours=32,
                start_week=2,
                end_week=17,
                status=status,
            )
            if suffix == "ready" and formation_source is not None:
                row.source_program_course_id = formation_source.id
                row.formation_mode = "SELECTABLE"
            db.add(row); db.flush()
            return row

        ready = task(task_batch, course, "READY", "ready")
        not_ready = task(task_batch, course, "DRAFT", "draft")
        wrong_course = task(task_batch, other_course, "READY", "course")
        wrong_term = task(other_task_batch, course, "READY", "term")

        result = {
            "term": int(term.id),
            "course": int(course.id),
            "ready": int(ready.id),
            "notReady": int(not_ready.id),
            "wrongCourse": int(wrong_course.id),
            "wrongTerm": int(wrong_term.id),
            "teacherName": ready.teacher_name,
        }
        db.commit()
        return result
    finally:
        db.close()


def _batch(client, admin, term_id):
    response = client.post(
        f"{BASE}/selection/batches",
        headers=admin,
        json={"batchName": f"W4任务身份批次-{term_id}", "termId": str(term_id)},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["batchId"]


def _add(client, admin, batch_id, course_id, task_id="__MISSING__"):
    body = {"courseId": str(course_id), "capacity": 40, "minCapacity": 1}
    if task_id != "__MISSING__":
        body["teachingTaskId"] = str(task_id)
    return client.post(
        f"{BASE}/selection/batches/{batch_id}/courses",
        headers=admin,
        json=body,
    )


def test_w4_missing_teaching_task_fails_closed(client, db_mode):
    facts = _seed(db_mode)
    admin = _admin(client)
    response = _add(client, admin, _batch(client, admin, facts["term"]), facts["course"])
    assert response.status_code == 409, response.text
    assert "READY" in response.text and "教学任务" in response.text


def test_w4_unknown_teaching_task_fails_closed(client, db_mode):
    facts = _seed(db_mode)
    admin = _admin(client)
    response = _add(
        client, admin, _batch(client, admin, facts["term"]), facts["course"], 999999999999,
    )
    assert response.status_code == 404, response.text
    assert "教学任务" in response.text


def test_w4_non_ready_task_fails_closed(client, db_mode):
    facts = _seed(db_mode)
    admin = _admin(client)
    response = _add(
        client, admin, _batch(client, admin, facts["term"]), facts["course"], facts["notReady"],
    )
    assert response.status_code == 409, response.text
    assert "READY" in response.text


def test_w4_task_course_mismatch_fails_closed(client, db_mode):
    facts = _seed(db_mode)
    admin = _admin(client)
    response = _add(
        client, admin, _batch(client, admin, facts["term"]), facts["course"], facts["wrongCourse"],
    )
    assert response.status_code == 409, response.text
    assert "课程" in response.text and "不一致" in response.text


def test_w4_task_term_mismatch_fails_closed(client, db_mode):
    facts = _seed(db_mode)
    admin = _admin(client)
    response = _add(
        client, admin, _batch(client, admin, facts["term"]), facts["course"], facts["wrongTerm"],
    )
    assert response.status_code == 409, response.text
    assert "学期" in response.text and "同一" in response.text


def test_w4_ready_same_course_same_term_is_persisted(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaSelectionCourse

    facts = _seed(db_mode)
    admin = _admin(client)
    response = _add(
        client, admin, _batch(client, admin, facts["term"]), facts["course"], facts["ready"],
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["teachingTaskId"] == str(facts["ready"])
    assert payload["courseId"] == str(facts["course"])
    assert payload["teacherName"] == facts["teacherName"]

    db = get_sessionmaker()()
    try:
        row = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.tenant_id == TID,
            AaSelectionCourse.id == int(payload["selectionCourseId"]),
        ).one()
        assert int(row.course_id) == facts["course"]
        assert int(row.teaching_task_id) == facts["ready"]
        assert row.teacher_name == facts["teacherName"]
    finally:
        db.close()


def test_w4_formal_router_has_no_legacy_add_course_bypass():
    router_source = (_ROOT / "app/modules/academic_affairs/routers/course_selection_router.py").read_text(encoding="utf-8")
    command_source = (_ROOT / "app/modules/academic_affairs/services/academic_affairs_selection_course_command_service.py").read_text(encoding="utf-8")

    assert "selection_course_command_svc.add_course(user, batchId, body)" in router_source
    assert "selection_svc.add_course(user, batchId, body)" not in router_source
    assert "AaTeachingTaskBatch" in command_source
    assert "task.status" in command_source and '"READY"' in command_source
    assert "task.course_id" in command_source
    assert "task_batch.term_id" in command_source
    assert "_guard_selection_formation(db, task_id)" in command_source
