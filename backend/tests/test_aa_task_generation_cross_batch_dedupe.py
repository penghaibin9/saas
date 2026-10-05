"""跨已完成批次补生成课程时不得重复建立同一学期课程任务。"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest
from pydantic import BaseModel, Field, ValidationError
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


def test_generation_class_id_preserves_large_string_and_rejects_invalid_values():
    # Execute the actual DTO without importing router registrations or DB fixtures.
    source = Path(__file__).parents[1] / "app/modules/academic_affairs/routers/academic_affairs.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    definition = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TaskBatchGenerate")
    namespace = {"BaseModel": BaseModel, "Field": Field, "Optional": Optional}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), str(source), "exec"), namespace)
    model = namespace["TaskBatchGenerate"]
    model.model_rebuild(_types_namespace=namespace)
    identity = "9007199254740993"
    assert model(termId="52", classId=identity).classId == identity
    assert model(termId="52").classId is None
    assert model(termId="52", classId=None).classId is None
    for invalid in ("", "0", "01", "-1", "1.5", " 1", "1\n", "１", True, 1):
        with pytest.raises(ValidationError):
            model(termId="52", classId=invalid)


def test_requested_generation_class_is_tenant_college_scoped_and_locked(monkeypatch):
    row = SimpleNamespace(id=9007199254740993)

    class Capture:
        statement = None

        def scalars(self, statement):
            self.statement = statement
            return SimpleNamespace(first=lambda: row)

    db = Capture()
    monkeypatch.setattr(generation, "_tid", lambda: TID)
    assert generation._requested_generation_class(db, str(row.id), 128) is row
    sql = str(db.statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "t_class.id = 9007199254740993" in sql
    for table in ("t_class", "t_major", "t_college"):
        assert f"{table}.tenant_id = {TID}" in sql
        assert f"{table}.is_deleted IS false" in sql
        assert f"{table}.status = 'ACTIVE'" in sql
    assert "t_class.class_status = 'NORMAL'" in sql
    assert "t_major.college_id = 128" in sql
    assert "FOR UPDATE" in sql
    assert generation._requested_generation_class(db, None, 128) is None
    db.scalars = lambda _statement: SimpleNamespace(first=lambda: None)
    from app.core.exceptions import AppException
    with pytest.raises(AppException) as rejected:
        generation._requested_generation_class(db, "4670", 128)
    assert rejected.value.code == "NO_DATA_SCOPE"
    for invalid in ("", "0", "-1", "1.5", True, 1):
        with pytest.raises(AppException) as invalid_id:
            generation._requested_generation_class(db, invalid, 128)
        assert invalid_id.value.code == "VALIDATION_ERROR"


def _scoped_generation_story(client, db_mode, monkeypatch):
    """Old duplicate pairs coexist with an independent, formally bound new class."""
    from app.core.config import settings
    from app.core.tenant_context import invalidate_tenant_cache
    from app.db.session import get_sessionmaker
    from app.models import Major, SchoolClass

    monkeypatch.setattr(settings, "MOCK_LOGIN_ENABLED", "true")
    monkeypatch.setattr(settings, "DEMO_TENANT_READONLY", "false")
    ids = _seed(db_mode, grade="2026", two=True)
    old_task_ids = []
    with get_sessionmaker()() as db:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(id=TID, tenant_code="demo", school_name="班级生成回归学校", status="ACTIVE"))
            db.commit()
    invalidate_tenant_cache("demo")
    school = _hdr(client, "school_admin01")
    course_id = int(_enabled_course(client, school, code="TGCS101", name="独立选修课"))
    college_id = int(ensure_course_review_college())
    with get_sessionmaker()() as db:
        db.get(Major, ids["major"]).college_id = college_id
        db.commit()
    program_id = _program(client, school, major_id=ids["major"], grade_year="2026", total_credits=4,
                          courses=[(course_id, "独立选修课", 4, 1)],
                          bindings=[("2026", ids["class1"]), ("2026", ids["class2"])], name="独立班级选课方案")
    term_id = int(_term(client, school, year_code="2026-2027", term_no=1))
    outside = _seed(db_mode, grade="2026")
    with get_sessionmaker()() as db:
        source = db.query(AaProgramCourse).filter(AaProgramCourse.tenant_id == TID,
                                                 AaProgramCourse.program_id == int(program_id)).one()
        source.formation_mode = "SELECTABLE"
        for number in range(2):
            batch = AaTeachingTaskBatch(tenant_id=TID, term_id=term_id, college_id=college_id,
                                        batch_name=f"保留历史批次{number}", status="APPROVED")
            db.add(batch); db.flush()
            task = AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=course_id,
                                  class_id=ids["class1"], source_program_course_id=source.id,
                                  formation_mode="SELECTABLE", status="READY")
            db.add(task); db.flush()
            old_task_ids.append(int(task.id))
        foreign = SchoolClass(tenant_id=TID + 1, major_id=ids["major"], class_name="其它租户班", grade="2026", status="ACTIVE")
        db.add(foreign); db.flush()
        foreign_id = int(foreign.id)
        unbound = SchoolClass(tenant_id=TID, major_id=ids["major"], class_name="无绑定独立班", grade="2026", status="ACTIVE")
        db.add(unbound); db.flush()
        unbound_id = int(unbound.id)
        source_id = int(source.id)
        db.commit()
    return {**ids, "term": term_id, "owner": college_id, "course": course_id,
            "outside": outside["class"], "foreign": foreign_id, "unbound": unbound_id,
            "oldTasks": old_task_ids, "source": source_id, "header": school}


def _generation_counts(term_id):
    from app.db.session import get_sessionmaker
    with get_sessionmaker()() as db:
        batches = db.query(AaTeachingTaskBatch.id).filter(AaTeachingTaskBatch.tenant_id == TID,
                                                          AaTeachingTaskBatch.term_id == term_id).all()
        tasks = db.query(AaTeachingTask.id).filter(AaTeachingTask.tenant_id == TID,
                                                   AaTeachingTask.batch_id.in_([row[0] for row in batches])).all()
        return len(batches), len(tasks)


def test_class_scoped_generation_preserves_old_duplicates_and_is_idempotent(client, db_mode, monkeypatch):
    story = _scoped_generation_story(client, db_mode, monkeypatch)
    body = {"termId": str(story["term"]), "collegeId": str(story["owner"]), "classId": str(story["class2"])}
    first = client.post(f"{BASE}/teaching-task-batches/generate", headers=story["header"], json=body)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["tasksGenerated"] == 1
    batch_id = first.json()["data"]["batchId"]
    tasks = _tasks(client, story["header"], batch_id)
    assert len(tasks) == 1
    assert str(tasks[0]["classId"]) == str(story["class2"])
    assert str(tasks[0]["courseId"]) == str(story["course"])
    assert _generation_counts(story["term"]) == (3, 3)
    again = client.post(f"{BASE}/teaching-task-batches/generate", headers=story["header"], json=body)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["batchId"] == batch_id
    assert again.json()["data"]["tasksGenerated"] == 0
    assert _generation_counts(story["term"]) == (3, 3)
    from app.db.session import get_sessionmaker
    with get_sessionmaker()() as db:
        old = db.query(AaTeachingTask).filter(AaTeachingTask.tenant_id == TID,
                                               AaTeachingTask.id.in_(story["oldTasks"])).all()
        assert len(old) == 2
        assert all(row.status == "READY" and row.class_id == story["class1"]
                   and row.source_program_course_id == story["source"] for row in old)
        generated = db.get(AaTeachingTask, int(tasks[0]["taskId"]))
        assert generated.formation_mode == "SELECTABLE"
        assert generated.source_program_course_id == story["source"]


def test_target_duplicates_and_unscoped_generation_still_conflict_without_writes(client, db_mode, monkeypatch):
    story = _scoped_generation_story(client, db_mode, monkeypatch)
    for target in (None, story["class1"]):
        body = {"termId": str(story["term"]), "collegeId": str(story["owner"])}
        if target is not None:
            body["classId"] = str(target)
        response = client.post(f"{BASE}/teaching-task-batches/generate", headers=story["header"], json=body)
        assert response.status_code == 409, response.text
        assert response.json()["details"]["blocker"] == "TASK_GENERATION_EXISTING_TASK_CONFLICT"
        assert _generation_counts(story["term"]) == (2, 2)


def test_generation_rejects_foreign_and_other_college_classes_without_writes(client, db_mode, monkeypatch):
    story = _scoped_generation_story(client, db_mode, monkeypatch)
    for target in (story["foreign"], story["outside"]):
        response = client.post(f"{BASE}/teaching-task-batches/generate", headers=story["header"],
                               json={"termId": str(story["term"]), "collegeId": str(story["owner"]), "classId": str(target)})
        assert response.status_code == 403, response.text
        assert response.json()["bizCode"] == "NO_DATA_SCOPE"
        assert _generation_counts(story["term"]) == (2, 2)
    missing_binding = client.post(f"{BASE}/teaching-task-batches/generate", headers=story["header"],
                                  json={"termId": str(story["term"]), "collegeId": str(story["owner"]), "classId": str(story["unbound"])})
    assert missing_binding.status_code == 409, missing_binding.text
    assert missing_binding.json()["bizCode"] == "PROGRAM_NOT_READY"
    assert _generation_counts(story["term"]) == (2, 2)
