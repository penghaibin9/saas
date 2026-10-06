"""V5 精确任务/应开责任关系；只在独立 MySQL 测试库运行。"""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, update

from app.core.context import get_tenant, set_tenant
from app.db.session import get_sessionmaker
from app.models import (AaCourse, AaProgram, AaProgramBinding, AaProgramCourse,
                        AaTeachingTask, AaTeachingTaskBatch, AaTerm, College, Major, SchoolClass)
from app.modules.academic_affairs.services import academic_affairs_responsibility_service as service

TID = 1000000000000000001


@pytest.fixture
def facts(db_mode):
    previous = get_tenant()
    set_tenant(TID)
    db = get_sessionmaker()()
    suffix = uuid4().hex[:10]
    college = College(tenant_id=TID, college_name="关系责任学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="关系责任专业", status="ACTIVE")
    db.add(major); db.flush()
    clazz = SchoolClass(tenant_id=TID, major_id=major.id, class_name="关系责任行政班",
                        grade="2026", status="ACTIVE", class_status="NORMAL")
    term = AaTerm(tenant_id=TID, year_code="2026-2027", term_no=1,
                  end_date=datetime(2027, 1, 31), status="PUBLISHED")
    course = AaCourse(tenant_id=TID, course_code=f"REL-{suffix}", course_name="专业课",
                      category="MAJOR_CORE", status="ENABLED")
    program = AaProgram(tenant_id=TID, program_name="正式责任方案", major_id=major.id,
                        grade_year="2026", status="PUBLISHED")
    db.add_all([clazz, term, course, program]); db.flush()
    binding = AaProgramBinding(tenant_id=TID, major_id=major.id, grade_year="2026",
                               program_id=program.id, bound_at=datetime(2026, 8, 1), status="ACTIVE")
    source = AaProgramCourse(tenant_id=TID, program_id=program.id, course_id=course.id,
                             open_term_no=1, formation_mode="ADMIN_FIXED")
    batch = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="已批准无学院旧批次",
                                status="APPROVED")
    db.add_all([binding, source, batch]); db.flush()
    task = AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=course.id,
                          class_id=clazz.id, status="READY")
    db.add(task); db.commit()
    try:
        yield db, dict(college=college, major=major, clazz=clazz, term=term, course=course,
                       program=program, binding=binding, source=source, batch=batch, task=task)
    finally:
        db.rollback(); db.close(); set_tenant(previous)


def _opening(rows):
    return [{"courseId": str(rows["course"].id), "classId": str(rows["clazz"].id),
             "programCourseId": str(rows["source"].id)}]


@pytest.mark.parametrize("invalid", [False, True])
def test_shared_term_projection_validates_handoff_before_excluding_successor(facts, invalid):
    from app.core.exceptions import AppException
    from app.models import AaTeachingTaskSourceHandoff

    db, rows = facts
    original = rows["task"]
    original.source_program_course_id = rows["source"].id
    newer = AaProgram(tenant_id=TID, major_id=rows["major"].id, grade_year="2026",
        program_name="承接后继正式版本", status="PUBLISHED")
    db.add(newer); db.flush()
    source = AaProgramCourse(tenant_id=TID, program_id=newer.id, course_id=rows["course"].id,
        open_term_no=1, formation_mode="ADMIN_FIXED")
    db.add(source); db.flush()
    successor = AaTeachingTask(tenant_id=TID, batch_id=rows["batch"].id,
        course_id=rows["course"].id, class_id=rows["clazz"].id, status="READY",
        source_program_course_id=source.id)
    db.add(successor); db.flush()
    db.add(AaTeachingTaskSourceHandoff(tenant_id=TID, term_id=rows["term"].id,
        execution_task_id=original.id, successor_task_id=successor.id,
        execution_source_id=source.id if invalid else rows["source"].id,
        successor_source_id=source.id, source_fingerprint="0" * 64,
        reason="隔离库承接关联校验", confirmed_by=1, idempotency_key=uuid4().hex,
        payload_hash="0" * 64))
    db.flush()
    if invalid:
        with pytest.raises(AppException) as denied:
            service.resolve_term_task_offering_colleges(db, rows["term"].id, cache={})
        assert denied.value.http_status == 409
        assert denied.value.details["blocker"] == "TASK_HANDOFF_REFERENCE_INVALID"
    else:
        assert service.resolve_term_task_offering_colleges(db, rows["term"].id, cache={}) == {
            int(original.id): int(rows["college"].id)}


def test_exact_major_grade_chain_and_explicit_task_source(facts):
    db, rows = facts
    task, college = rows["task"], rows["college"]
    assert service.resolve_task_offering_colleges(db, [task])[task.id] == college.id
    task.source_program_course_id = rows["source"].id
    db.flush()
    assert service.resolve_task_offering_colleges(db, [str(task.id)])[task.id] == college.id
    assert service.resolve_opening_offering_colleges(db, rows["term"], _opening(rows)) == {
        (rows["course"].id, rows["clazz"].id): college.id}


def test_class_override_uses_exact_override_program_course(facts):
    db, rows = facts
    override = AaProgram(tenant_id=TID, major_id=rows["major"].id, grade_year="2026",
                         program_name="班级特例方案", status="FROZEN")
    db.add(override); db.flush()
    source = AaProgramCourse(tenant_id=TID, program_id=override.id,
                             course_id=rows["course"].id, open_term_no=1)
    db.add(source)
    db.add(AaProgramBinding(tenant_id=TID, major_id=rows["major"].id, grade_year="2026",
                           class_id=rows["clazz"].id, program_id=override.id,
                           bound_at=datetime(2026, 8, 2), status="ACTIVE"))
    db.flush()
    task = rows["task"]
    task.source_program_course_id = rows["source"].id
    db.flush()
    assert service.resolve_task_offering_colleges(db, [task])[task.id] is None
    task.source_program_course_id = source.id
    db.flush()
    assert service.resolve_task_offering_colleges(db, [task])[task.id] == rows["college"].id


@pytest.mark.parametrize("case", ["cross_tenant", "cross_tenant_class", "cross_tenant_program", "cross_tenant_source",
    "cross_tenant_major", "cross_tenant_college", "class_grade", "program_grade", "binding_grade",
    "wrong_term", "multiple_bindings", "future_binding", "inactive_college", "inactive_major",
    "disabled_program", "non_null_owner", "non_null_batch", "source_mismatch", "missing_class",
    "merged", "unapproved", "public", "historical_diff", "duplicate_course", "no_term_end"])
def test_task_relation_rejects_unproven_or_explicit_sources(facts, case):
    db, rows = facts
    task = rows["task"]
    if case == "cross_tenant": rows["binding"].tenant_id = TID + 10
    elif case.startswith("cross_tenant_"):
        name = {"class": "clazz", "program": "program", "source": "source", "major": "major", "college": "college"}[case.removeprefix("cross_tenant_")]
        rows[name].tenant_id = TID + 10
    elif case == "class_grade": rows["clazz"].grade = "2025"
    elif case == "program_grade": rows["program"].grade_year = "2025"
    elif case == "binding_grade": rows["binding"].grade_year = "2025"
    elif case == "wrong_term": rows["source"].open_term_no = 2
    elif case == "multiple_bindings":
        db.add(AaProgramBinding(tenant_id=TID, major_id=rows["major"].id, grade_year="2026",
            program_id=rows["program"].id, bound_at=datetime(2026, 8, 1), status="ACTIVE"))
    elif case == "future_binding": rows["binding"].bound_at = datetime.utcnow() + timedelta(days=30)
    elif case == "inactive_college": rows["college"].status = "DISABLED"
    elif case == "inactive_major": rows["major"].status = "DISABLED"
    elif case == "disabled_program": rows["program"].status = "DISABLED"
    elif case == "non_null_owner": rows["course"].owner_college_id = 987654321
    elif case == "non_null_batch": rows["batch"].college_id = 987654321
    elif case == "source_mismatch": task.source_program_course_id = 987654321
    elif case == "missing_class": task.class_id = None
    elif case == "merged": task.is_merged = True
    elif case == "unapproved": rows["batch"].status = "DRAFT"
    elif case == "public": rows["course"].category = "PUBLIC_BASIC"
    elif case == "historical_diff":
        rows["term"].end_date = datetime(2026, 7, 31)
    elif case == "duplicate_course":
        db.add(AaProgramCourse(tenant_id=TID, program_id=rows["program"].id,
                              course_id=rows["course"].id, open_term_no=1))
    elif case == "no_term_end": rows["term"].end_date = None
    db.flush()
    assert service.resolve_task_offering_colleges(db, [task.id]) == {task.id: None}


def test_opening_cannot_override_cross_college_approved_batch(facts):
    db, rows = facts
    rows["batch"].college_id = 987654321
    db.flush()
    key = (rows["course"].id, rows["clazz"].id)
    assert service.resolve_opening_offering_colleges(db, rows["term"], _opening(rows))[key] is None
    rows["task"].is_deleted = True
    db.flush()
    assert service.resolve_opening_offering_colleges(db, rows["term"], _opening(rows))[key] == rows["college"].id
    rows["course"].owner_college_id = 987654321
    db.flush()
    assert service.resolve_opening_offering_colleges(db, rows["term"], _opening(rows))[key] is None


@pytest.mark.parametrize("explicit_batch", [False, True])
def test_opening_request_reuses_exact_owners_across_colleges_and_isolates_terms(facts, explicit_batch):
    from app.modules.academic_affairs.services.academic_affairs_archive_rule_evaluator import _expected_opening

    db, rows = facts
    other = College(tenant_id=TID, college_name="接收开课学院", status="ACTIVE")
    other_term = AaTerm(tenant_id=TID, year_code="2026-2027", term_no=2,
                        end_date=datetime(2027, 6, 30), status="PUBLISHED")
    db.add_all([other, other_term, AaProgramCourse(tenant_id=TID,
        program_id=rows["program"].id, course_id=rows["course"].id, open_term_no=2,
        formation_mode="ADMIN_FIXED")]); db.flush()
    if explicit_batch:
        rows["batch"].college_id = other.id
    db.commit()
    own_id, other_id = rows["college"].id, other.id
    pair = (rows["course"].id, rows["clazz"].id)
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", record)
    try:
        cache = {}
        own, _ = _expected_opening(db, rows["term"], college_ids={own_id}, cache=cache)
        assert {row["key"] for row in own} == (set() if explicit_batch else {pair})
        assert statements
        statements.clear()
        received, _ = _expected_opening(db, rows["term"], college_ids={other_id}, cache=cache)
        assert {row["key"] for row in received} == ({pair} if explicit_batch else set())
        assert not statements, "同一请求的其他学院应复用精确开课归属"
        # 同年级、同课程在另一学期没有这个显式任务批次，必须重新解析归属。
        fresh_term, _ = _expected_opening(db, other_term, college_ids={own_id}, cache=cache)
        assert {row["key"] for row in fresh_term} == {pair}
        assert statements
        with get_sessionmaker()() as writer:
            writer.execute(update(AaProgramBinding).where(
                AaProgramBinding.id == rows["binding"].id).values(status="REVOKED"))
            writer.commit()
        with get_sessionmaker()() as fresh_db:
            fresh, _ = _expected_opening(fresh_db, rows["term"], college_ids={own_id, other_id})
        assert not fresh, "新请求不能继续使用已撤销的方案绑定"
    finally:
        event.remove(db.bind, "before_cursor_execute", record)


def test_opening_first_read_batches_program_facts_across_majors_and_cohorts(facts):
    from app.modules.academic_affairs.services.academic_affairs_archive_rule_evaluator import _expected_opening

    db, rows = facts
    course_id, college_id = rows["course"].id, rows["college"].id
    term = rows["term"]
    term.year_code; term.term_no; term.end_date
    expected = {(course_id, rows["clazz"].id)}
    major_ids = {rows["major"].id}
    for index in range(5):
        grade = "2025" if index % 2 else "2026"
        major = Major(tenant_id=TID, college_id=college_id,
                      major_name=f"批量责任专业{index}", status="ACTIVE")
        db.add(major); db.flush()
        major_ids.add(major.id)
        clazz = SchoolClass(tenant_id=TID, major_id=major.id, class_name=f"批量责任班{index}",
                            grade=grade, status="ACTIVE", class_status="NORMAL")
        program = AaProgram(tenant_id=TID, major_id=major.id, grade_year=grade,
                            program_name=f"批量正式方案{index}", status="PUBLISHED")
        db.add_all([clazz, program]); db.flush()
        db.add_all([AaProgramBinding(tenant_id=TID, major_id=major.id, grade_year=grade,
            program_id=program.id, bound_at=datetime(2026, 8, 1), status="ACTIVE"),
            AaProgramCourse(tenant_id=TID, program_id=program.id, course_id=course_id,
                open_term_no=3 if grade == "2025" else 1, formation_mode="ADMIN_FIXED")])
        expected.add((course_id, clazz.id))
    db.flush()
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", record)
    try:
        cache = {}
        actual, structural = _expected_opening(db, term, college_ids={college_id}, major_ids=major_ids, cache=cache)
        assert {row["key"] for row in actual} == expected
        assert not structural
        assert len(statements) <= 18, "首轮应开读取不能随专业和方案逐个查询"
        statements.clear()
        school, structural = _expected_opening(db, term, major_ids=major_ids, cache=cache)
        assert {row["key"] for row in school} == expected
        assert not structural and not statements
        other, structural = _expected_opening(db, term, college_ids={college_id + 1000000}, major_ids=major_ids, cache=cache)
        assert not other and not structural and not statements
    finally:
        event.remove(db.bind, "before_cursor_execute", record)


def test_batch_resolution_has_constant_queries_and_checks_each_task_source(facts):
    db, rows = facts
    tasks = [AaTeachingTask(tenant_id=TID, batch_id=rows["batch"].id, course_id=rows["course"].id,
        class_id=rows["clazz"].id, source_program_course_id=rows["source"].id if i % 2 == 0 else 987654321,
        status="READY") for i in range(384)]
    db.add_all(tasks); db.flush()
    task_ids = [task.id for task in tasks]
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", record)
    try:
        cache = {}
        result = service.resolve_task_offering_colleges(db, task_ids, cache=cache)
        assert len(statements) <= 10, len(statements)
        assert result == {task_id: rows["college"].id if i % 2 == 0 else None
                          for i, task_id in enumerate(task_ids)}
        statements.clear()
        assert service.resolve_task_offering_colleges(db, task_ids, cache=cache) == result
        assert not statements
    finally:
        event.remove(db.bind, "before_cursor_execute", record)


@pytest.mark.parametrize("model,field,value", [(AaProgram, "status", "DISABLED"),
    (AaProgramBinding, "status", "SUPERSEDED"), (College, "status", "DISABLED"),
    (SchoolClass, "status", "DISABLED")])
def test_publish_locks_refresh_cached_authority(facts, model, field, value):
    db, rows = facts
    cache = {}
    task_id = rows["task"].id
    assert service.resolve_task_offering_colleges(db, [task_id], cache=cache)[task_id] == rows["college"].id
    by_model = {AaProgram: rows["program"], AaProgramBinding: rows["binding"],
                College: rows["college"], SchoolClass: rows["clazz"]}
    with get_sessionmaker()() as writer:
        writer.execute(update(model).where(model.id == by_model[model].id).values({field: value}))
        writer.commit()
    assert service.resolve_task_offering_colleges(db, [task_id], cache=cache, lock=True)[task_id] is None


def test_publish_rejects_class_relation_moved_after_snapshot(facts):
    from app.core.exceptions import AppException
    db, rows = facts
    replacement = Major(tenant_id=TID, college_id=rows["college"].id,
                        major_name="关系变更专业", status="ACTIVE")
    db.add(replacement); db.commit()
    changed = []
    def move_before_class_lock(conn, cursor, statement, parameters, context, executemany):
        if not changed and "t_class" in statement and "FOR UPDATE" in statement.upper():
            changed.append(True)
            with get_sessionmaker()() as writer:
                writer.execute(update(SchoolClass).where(SchoolClass.id == rows["clazz"].id)
                               .values(major_id=replacement.id))
                writer.commit()
    event.listen(db.bind, "before_cursor_execute", move_before_class_lock)
    try:
        with pytest.raises(AppException):
            service.resolve_task_offering_colleges(db, [rows["task"].id], lock=True)
        assert changed
    finally:
        event.remove(db.bind, "before_cursor_execute", move_before_class_lock)


@pytest.mark.parametrize("blocker", ["draft", "recheck", "change"])
def test_college_grade_closure_keeps_third_layer_tasks(facts, blocker):
    from app.models import AaGradeRecord, AaGradeRecheck, AaGradeTask, AcademicGrade, StudentProfile, WorkflowInstance
    from app.modules.academic_affairs.services.academic_affairs_archive_rule_evaluator import evaluate_grade

    db, rows = facts
    student_id = db.query(StudentProfile.id).filter(StudentProfile.tenant_id == TID).first()[0]
    term_code = "2026-2027-1"
    task = AaGradeTask(tenant_id=TID, teaching_task_id=rows["task"].id,
        term_id=rows["term"].id, term_code=term_code,
        status="DRAFT" if blocker == "draft" else "PUBLISHED")
    grade = AcademicGrade(tenant_id=TID, acad_student_id=1, course_name="关系责任成绩", term=term_code)
    db.add_all([task, grade]); db.flush()
    record = AaGradeRecord(tenant_id=TID, task_id=task.id, student_id=student_id, acad_grade_id=grade.id)
    db.add(record); db.flush()
    if blocker == "recheck":
        db.add(AaGradeRecheck(tenant_id=TID, student_id=student_id, acad_grade_id=grade.id,
            reason="隔离归档反例", status="SUBMITTED"))
    if blocker == "change":
        db.add(WorkflowInstance(tenant_id=TID, workflow_code="AA_GRADE_CHANGE", source_module="academic-affairs",
            source_biz_type="AA_GRADE_CHANGE", source_biz_id=record.id, applicant_id=1,
            title="隔离成绩更正", status="RUNNING"))
    other = College(tenant_id=TID, college_name="其他学院", status="ACTIVE")
    db.add(other); db.commit()
    base = {"present": True, "recordCount": 1, "remark": "原成绩政策检查通过"}
    result = evaluate_grade(db, term_code, base, college_ids=[rows["college"].id], term_id=rows["term"].id)
    evidence = result["evidence"][0]
    assert result["result"] == "BLOCKED", result
    assert evidence["taskCount"] == 1 and evidence["missingGradeTaskCount"] == 0, result
    assert result["ruleCode"] == {"draft": "GRADE_TASK_UNPUBLISHED", "recheck": "GRADE_RECHECK_ACTIVE",
        "change": "GRADE_CHANGE_ACTIVE"}[blocker], result
    outside = evaluate_grade(db, term_code, base, college_ids=[other.id], term_id=rows["term"].id)["evidence"][0]
    assert outside["taskCount"] == outside["activeRechecks"] == outside["activeChanges"] == 0, outside


def test_opening_source_lock_prevents_new_course_until_publish_transaction_finishes(facts):
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from app.modules.academic_affairs.services.academic_affairs_schedule_gate_service import _opening_source_fingerprint

    db, rows = facts
    before = _opening_source_fingerprint(db, rows["term"].id, lock=True)
    with get_sessionmaker()() as writer:
        writer.execute(text("SET SESSION innodb_lock_wait_timeout=1"))
        writer.add(AaProgramCourse(tenant_id=TID, program_id=rows["program"].id,
            course_id=rows["course"].id, open_term_no=2))
        with pytest.raises(OperationalError) as failure:
            writer.commit()
        assert failure.value.orig.args[0] == 1205
        writer.rollback()
    assert _opening_source_fingerprint(db, rows["term"].id, lock=True) == before
