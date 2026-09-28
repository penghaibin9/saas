"""跨已完成批次补生成课程时不得重复建立同一学期课程任务。"""
from __future__ import annotations

from sqlalchemy.dialects import mysql

from app.models import AaProgramCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm, Tenant
from app.modules.academic_affairs.services import academic_affairs_task_generation_service as generation
from test_aa_teaching_task import (
    BASE,
    TID,
    _enabled_course,
    _hdr,
    _program,
    _seed,
    _tasks,
    _term,
    ensure_course_review_college,
)


def _generate(client, school_header, term_id, college_id):
    return client.post(
        f"{BASE}/teaching-task-batches/generate",
        headers=school_header,
        json={"termId": str(term_id), "collegeId": str(college_id)},
    )


def test_generate_after_approved_batch_skips_existing_and_only_repairs_missing_task(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.core.config import settings

    monkeypatch.setattr(settings, "MOCK_LOGIN_ENABLED", "true")
    monkeypatch.setattr(settings, "DEMO_TENANT_READONLY", "false")

    ids = _seed(db_mode, grade="2026")
    with get_sessionmaker()() as db:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(id=TID, tenant_code="demo", school_name="教务生成回归学校", status="ACTIVE"))
            db.commit()
    from app.core.tenant_context import invalidate_tenant_cache
    invalidate_tenant_cache("demo")
    school = _hdr(client, "school_admin01")
    core_course_id = _enabled_course(client, school, code="TGD101", name="核心课")
    elective_course_id = _enabled_course(client, school, code="TGD102", name="选修课")
    college_id = int(ensure_course_review_college())
    program_id = _program(
        client,
        school,
        major_id=ids["major"],
        grade_year="2026",
        total_credits=8,
        courses=[(core_course_id, "核心课", 4, 1), (elective_course_id, "选修课", 4, 2)],
        bindings=[("2026", ids["class"])],
        name="跨批去重回归方案",
    )
    term_id = _term(client, school, year_code="2026-2027", term_no=1)

    first = _generate(client, school, term_id, college_id)
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    assert first_data["tasksGenerated"] == 1
    first_tasks = _tasks(client, school, first_data["batchId"])
    assert len(first_tasks) == 1

    # Repeating generation in the same editable batch preserves the existing
    # idempotent contract: 200 with zero newly generated tasks.
    repeated_draft = _generate(client, school, term_id, college_id)
    assert repeated_draft.status_code == 200, repeated_draft.text
    assert repeated_draft.json()["data"]["batchId"] == first_data["batchId"]
    assert repeated_draft.json()["data"]["tasksGenerated"] == 0
    assert repeated_draft.json()["data"]["tasksSkippedExisting"] == 1

    college = _hdr(client, "college_admin01")
    teacher = _hdr(client, "academic01")
    for task in first_tasks:
        assigned = client.post(
            f"{BASE}/teaching-tasks/{task['taskId']}/assign",
            headers=college,
            json={"teacherName": "赵敏", "teacherKey": "academic01", "expectedStudents": 30},
        )
        assert assigned.status_code == 200, assigned.text
        confirmed = client.post(
            f"{BASE}/teaching-tasks/{task['taskId']}/teacher-act",
            headers=teacher,
            json={"action": "CONFIRM"},
        )
        assert confirmed.status_code == 200, confirmed.text
    submitted = client.post(
        f"{BASE}/teaching-task-batches/{first_data['batchId']}/submit", headers=college,
    )
    assert submitted.status_code == 200, submitted.text
    approved = client.post(
        f"{BASE}/teaching-task-batches/{first_data['batchId']}/review",
        headers=school,
        json={"action": "APPROVE"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "APPROVED"

    # With no editable batch, all targets already covered by an approved batch
    # must conflict rather than creating a misleading empty batch.
    already_done = _generate(client, school, term_id, college_id)
    assert already_done.status_code == 409, already_done.text
    assert already_done.json()["details"]["blocker"] == "TASK_GENERATION_ALREADY_EXISTS"
    with get_sessionmaker()() as db:
        assert db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.tenant_id == TID,
            AaTeachingTaskBatch.term_id == int(term_id),
            AaTeachingTaskBatch.college_id == college_id,
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).count() == 1

    # Isolated test data: move the existing elective into this term after approval.
    # The published plan's total credits and course identity remain unchanged.
    with get_sessionmaker()() as db:
        elective = db.query(AaProgramCourse).filter(
            AaProgramCourse.tenant_id == TID,
            AaProgramCourse.program_id == int(program_id),
            AaProgramCourse.course_id == int(elective_course_id),
            AaProgramCourse.is_deleted.is_(False),
        ).one()
        elective.open_term_no = 1
        db.commit()

    repaired = _generate(client, school, term_id, college_id)
    assert repaired.status_code == 200, repaired.text
    repaired_data = repaired.json()["data"]
    assert repaired_data["batchId"] != first_data["batchId"]
    assert repaired_data["tasksGenerated"] == 1
    assert repaired_data["tasksSkippedExisting"] == 1
    new_tasks = _tasks(client, school, repaired_data["batchId"])
    assert len(new_tasks) == 1
    assert int(new_tasks[0]["courseId"]) == int(elective_course_id)

    with get_sessionmaker()() as db:
        live = db.query(AaTeachingTask).join(
            AaTeachingTaskBatch, AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
        ).filter(
            AaTeachingTask.tenant_id == TID,
            AaTeachingTaskBatch.tenant_id == TID,
            AaTeachingTaskBatch.term_id == int(term_id),
            AaTeachingTaskBatch.college_id == college_id,
            AaTeachingTask.is_deleted.is_(False),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).all()
        pairs = [(int(task.course_id), int(task.class_id)) for task in live]
        assert len(pairs) == 2
        assert len(set(pairs)) == 2
    assert set(course for course, _class_id in pairs) == {int(core_course_id), int(elective_course_id)}


def test_cross_batch_lookup_is_tenant_term_course_class_scoped_current_read(monkeypatch):
    class StatementCapture:
        statement = None

        def execute(self, statement):
            self.statement = statement

            class Result:
                @staticmethod
                def all():
                    return []

            return Result()

    db = StatementCapture()
    monkeypatch.setattr(generation, "_tid", lambda: TID)
    assert generation._existing_term_task_rows(db, term_id=9, course_id=71, class_id=81) == []
    sql = str(db.statement.compile(
        dialect=mysql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))
    assert "t_aa_teaching_task.tenant_id =" in sql
    assert "t_aa_teaching_task.course_id = 71" in sql
    assert "t_aa_teaching_task.class_id = 81" in sql
    assert "t_aa_teaching_task_batch.term_id = 9" in sql
    assert "t_aa_teaching_task.is_deleted IS false" in sql
    assert "t_aa_teaching_task_batch.is_deleted IS false" in sql
    assert "LIMIT 2 FOR UPDATE" in sql


def test_locked_term_refreshes_identity_map_after_concurrent_archive(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_archive_core_service as archive

    monkeypatch.setattr(generation, "_tid", lambda: TID)
    monkeypatch.setattr(archive, "_tid", lambda: TID)
    with get_sessionmaker()() as setup:
        term = AaTerm(
            id=900001,
            tenant_id=TID,
            year_code="2098-2099",
            term_no=1,
            term_name="并发封存回归学期",
            status="PUBLISHED",
            is_current=False,
        )
        setup.add(term)
        setup.commit()

    reader = get_sessionmaker()()
    try:
        cached = reader.get(AaTerm, 900001)
        assert cached is not None and cached.status == "PUBLISHED"
        archive.guard_term_writable(reader, 900001)

        with get_sessionmaker()() as archiver:
            concurrently_archived = archiver.get(AaTerm, 900001)
            assert concurrently_archived is not None
            concurrently_archived.status = "ARCHIVED"
            archiver.commit()

        locked = reader.scalars(generation._locked_term_statement(900001)).first()
        assert locked is cached
        assert locked.status == "ARCHIVED"
    finally:
        reader.close()
