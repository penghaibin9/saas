"""承接后继拒绝新增执行；隔离MySQL正式服务行为，不作为页面验收。"""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from tests.test_aa_task_source_review import _pair
from tests.test_aa_schedule import BASE, TID


@contextmanager
def _tenant():
    from app.core.context import get_tenant, set_tenant
    previous = get_tenant()
    set_tenant(TID)
    try:
        yield
    finally:
        set_tenant(previous)


def _handed_pair(client):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskSourceHandoff, User
    facts = _pair(client)
    with get_sessionmaker()() as db:
        original = db.get(AaTeachingTask, int(facts['oldId']))
        actor = db.query(User).filter_by(tenant_id=TID, login_name='school_admin01').one()
        facts['actor'] = {'userId': str(actor.id), 'currentRoleCode': 'SCHOOL_ADMIN', 'userType': 'STAFF'}
        facts['before'] = [(t.id, t.status, t.source_program_course_id, t.version)
            for t in db.query(AaTeachingTask).filter(AaTeachingTask.id.in_([int(facts['oldId']), int(facts['newId'])])).order_by(AaTeachingTask.id)]
        db.add(AaTeachingTaskSourceHandoff(tenant_id=TID, term_id=int(facts['termId']),
            execution_task_id=original.id, successor_task_id=int(facts['newId']),
            execution_source_id=original.source_program_course_id, successor_source_id=facts['newSourceId'],
            source_fingerprint='a' * 64, confirmed_by=actor.id, reason='隔离测试来源承接关系准备',
            idempotency_key='downstream-handoff-fixture', payload_hash='b' * 64))
        db.commit()
    return facts


def _unchanged(facts):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskSourceHandoff
    with get_sessionmaker()() as db:
        after = [(t.id, t.status, t.source_program_course_id, t.version)
            for t in db.query(AaTeachingTask).filter(AaTeachingTask.id.in_([int(facts['oldId']), int(facts['newId'])])).order_by(AaTeachingTask.id)]
        assert after == facts['before']
        assert db.query(AaTeachingTaskSourceHandoff).filter_by(tenant_id=TID, successor_task_id=int(facts['newId'])).count() == 1


def test_grade_creation_allows_execution_and_rejects_successor(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaGradeTask
    facts = _handed_pair(client)
    rejected = client.post(f'{BASE}/grade-tasks/identity', headers=facts['school'], json={'teachingTaskId': facts['newId']})
    assert rejected.status_code == 409, rejected.text
    allowed = client.post(f'{BASE}/grade-tasks/identity', headers=facts['school'], json={'teachingTaskId': facts['oldId']})
    assert allowed.status_code == 200, allowed.text
    with get_sessionmaker()() as db:
        assert not db.query(AaGradeTask).filter_by(tenant_id=TID, teaching_task_id=int(facts['newId'])).count()
        assert db.query(AaGradeTask).filter_by(tenant_id=TID, teaching_task_id=int(facts['oldId'])).count() == 1
    _unchanged(facts)


@pytest.mark.parametrize('operation', ['projection', 'legacy_projection', 'roster_version', 'legacy_roster_version', 'consumer_freeze', 'consumer_current'])
def test_existing_class_never_bypasses_successor_write_gate(client, db_mode, operation):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingClass, AaTeachingClassRosterVersion
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as classes
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_core_service as legacy
    from app.modules.academic_affairs.services import academic_affairs_roster_consumer_service as consumers
    facts = _handed_pair(client)
    with get_sessionmaker()() as db, _tenant():
        clazz = db.get(AaTeachingClass, facts['newClassId'])
        before = db.query(AaTeachingClassRosterVersion).filter_by(tenant_id=TID, teaching_class_id=clazz.id).count()
        with pytest.raises(AppException) as error:
            if operation == 'projection': classes.ensure_teaching_class_for_task(db, int(facts['newId']))
            elif operation == 'legacy_projection': legacy.ensure_teaching_class_for_task(db, int(facts['newId']))
            elif operation in ('roster_version', 'legacy_roster_version'):
                service = classes if operation == 'roster_version' else legacy
                service.create_roster_version(db, clazz, [711, 712], source_type='ADMIN_CLASS', source_id=clazz.source_id)
            elif operation == 'consumer_freeze': consumers.freeze_consumer_snapshot(db, 'GRADE_TASK', 987654, int(facts['newId']))
            else: consumers.require_consumer_snapshot_current(db, 'GRADE_TASK', 987654, int(facts['newId']))
        assert error.value.http_status == 409
        assert error.value.details['blocker'] == 'TASK_EXECUTION_HANDOFF'
        assert db.query(AaTeachingClassRosterVersion).filter_by(tenant_id=TID, teaching_class_id=clazz.id).count() == before
        # Historical roster reads stay available and keep their original task identity.
        assert classes.resolve_teaching_task_roster(db, int(facts['newId']))['ready'] is True
        assert classes.ensure_teaching_class_for_task(db, int(facts['oldId'])).teaching_task_id == int(facts['oldId'])
        db.rollback()
    _unchanged(facts)


def test_missing_projection_still_rejects_successor(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingClass
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_roster_consumer_service as consumers
    facts = _handed_pair(client)
    with get_sessionmaker()() as db, _tenant():
        db.get(AaTeachingClass, facts['newClassId']).is_deleted = True
        db.flush()
        with pytest.raises(AppException) as error:
            consumers.freeze_consumer_snapshot(db, 'ATTENDANCE_SESSION', 987654, int(facts['newId']))
        assert error.value.details['blocker'] == 'TASK_EXECUTION_HANDOFF'
        db.rollback()
    _unchanged(facts)


def test_formal_teacher_proxy_writes_original_and_rejects_successor(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaGradeTask, AaGradeRecord, AaTeachingTask
    from app.modules.academic_affairs.services import academic_affairs_grade_execution_service as execution
    from app.core.exceptions import AppException
    # Prepare both grade objects before the imported handoff relation; this deliberately
    # exercises defensive handling of an already-existing successor child object.
    facts = _pair(client)
    response = client.post(f'{BASE}/grade-tasks/identity', headers=facts['school'], json={'teachingTaskId': facts['oldId']})
    assert response.status_code == 200, response.text
    grade_ids = {'old': int(response.json()['data']['gradeTaskId'])}
    # An imported existing child is fixture preparation, not an identity endpoint
    # creating a second physical grade task for the same course and term.
    with get_sessionmaker()() as db:
        original_grade = db.get(AaGradeTask, grade_ids['old'])
        successor_grade = AaGradeTask(tenant_id=TID, teaching_task_id=int(facts['newId']),
            term_id=original_grade.term_id, term_code=original_grade.term_code,
            course_id=original_grade.course_id, course_name=original_grade.course_name,
            class_id=original_grade.class_id, teacher_key=original_grade.teacher_key,
            credit=original_grade.credit, usual_ratio=original_grade.usual_ratio,
            midterm_ratio=original_grade.midterm_ratio, final_ratio=original_grade.final_ratio,
            pass_line=original_grade.pass_line, status='NOT_STARTED')
        db.add(successor_grade)
        db.flush()
        grade_ids['new'] = successor_grade.id
        db.commit()
    from app.models import AaTeachingTaskSourceHandoff, User
    with get_sessionmaker()() as db:
        original = db.get(AaTeachingTask, int(facts['oldId']))
        actor = db.query(User).filter_by(tenant_id=TID, login_name='school_admin01').one()
        db.add(AaTeachingTaskSourceHandoff(tenant_id=TID, term_id=int(facts['termId']),
            execution_task_id=original.id, successor_task_id=int(facts['newId']),
            execution_source_id=original.source_program_course_id, successor_source_id=facts['newSourceId'],
            source_fingerprint='a' * 64, confirmed_by=actor.id, reason='隔离测试已有子对象防御检查',
            idempotency_key='teacher-proxy-handoff-fixture', payload_hash='b' * 64))
        teacher_key = original.teacher_key
        db.commit()
    teacher = {'userId': teacher_key, 'loginName': teacher_key, 'currentRoleCode': 'TEACHER', 'userType': 'STAFF'}
    body = SimpleNamespace(studentId=711, usualScore=80, finalScore=90, midtermScore=None, exceptionFlag='NORMAL')
    with _tenant():
        execution.teacher_enter_score(grade_ids['old'], teacher, body)
        with pytest.raises(AppException) as error:
            execution.teacher_enter_score(grade_ids['new'], teacher, body)
        assert error.value.http_status == 409
        assert error.value.details['blocker'] == 'TASK_EXECUTION_HANDOFF'
        unauthorized = {**teacher, 'userId': 'not-the-teacher', 'loginName': 'not-the-teacher'}
        with pytest.raises(AppException) as denied:
            execution.teacher_enter_score(grade_ids['new'], unauthorized, body)
        assert denied.value.http_status == 403
    with get_sessionmaker()() as db:
        assert db.query(AaGradeRecord).filter_by(tenant_id=TID, task_id=grade_ids['old']).count() == 1
        assert db.query(AaGradeRecord).filter_by(tenant_id=TID, task_id=grade_ids['new']).count() == 0
        assert db.get(AaGradeTask, grade_ids['new']).status == 'NOT_STARTED'


def test_waiting_old_teacher_is_rejected_after_formal_replacement_commits(client, db_mode, monkeypatch):
    """Real teacher-relation command holds Task; a canonical score writer waits then rechecks."""
    import re
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, local
    from sqlalchemy import event
    from app.db.session import get_sessionmaker, get_engine
    from app.models import AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask, AaGradeRecord
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_grade_execution_service as execution
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_teacher_service as teachers

    facts = _pair(client)
    response = client.post(f'{BASE}/grade-tasks/identity', headers=facts['school'], json={'teachingTaskId': facts['oldId']})
    assert response.status_code == 200, response.text
    grade_id = int(response.json()['data']['gradeTaskId'])
    with get_sessionmaker()() as db:
        task = db.get(AaTeachingTask, int(facts['oldId']))
        old_key = task.teacher_key
        clazz = db.query(AaTeachingClass).filter_by(tenant_id=TID, teaching_task_id=task.id, is_deleted=False).one()
        relation = db.query(AaTeachingClassTeacher).filter_by(tenant_id=TID, teaching_class_id=clazz.id, role_type='PRIMARY', status='ACTIVE', is_deleted=False).one()
        class_id, relation_id = clazz.id, relation.id
    new_key = facts['tasks'][1]['teacherKey']
    assert new_key != old_key
    held, waiting = Event(), Event()
    worker = local()
    original_update = teachers.update_relation
    def replacing(*args, **kwargs):
        worker.role = 'replacement'
        try:
            return original_update(*args, **kwargs)
        finally:
            worker.role = None
    def current_task(statement):
        return 'FOR UPDATE' in statement.upper() and re.search(r'\bFROM\s+t_aa_teaching_task\b', statement, re.I)
    def after_sql(conn, cursor, statement, parameters, context, executemany):
        if getattr(worker, 'role', None) == 'replacement' and not held.is_set() and current_task(statement):
            held.set()
            assert waiting.wait(10), '旧教师未进入共同任务锁等待窗口'
    def before_sql(conn, cursor, statement, parameters, context, executemany):
        if getattr(worker, 'role', None) == 'writer' and current_task(statement):
            waiting.set()
    def write_as_old_teacher():
        worker.role = 'writer'
        teacher = {'userId': old_key, 'loginName': old_key, 'currentRoleCode': 'TEACHER', 'userType': 'STAFF'}
        with _tenant():
            try:
                execution.teacher_enter_score(grade_id, teacher, SimpleNamespace(studentId=711, usualScore=80, finalScore=90, midtermScore=None, exceptionFlag='NORMAL'))
            except AppException as error:
                return error
        return None
    monkeypatch.setattr(teachers, 'update_relation', replacing)
    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', before_sql)
    event.listen(engine, 'after_cursor_execute', after_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            replacement = pool.submit(client.put, f'{BASE}/teaching-classes/{class_id}/teachers/{relation_id}', headers=facts['school'],
                json={'teacherKey': new_key, 'reason': '隔离并发回归正式更换任课教师'})
            assert held.wait(10), '正式教师替换未取得共同任务锁'
            writer = pool.submit(write_as_old_teacher)
            replaced = replacement.result(timeout=25)
            rejected = writer.result(timeout=25)
    finally:
        event.remove(engine, 'before_cursor_execute', before_sql)
        event.remove(engine, 'after_cursor_execute', after_sql)
    assert replaced.status_code == 200, replaced.text
    assert waiting.is_set()
    assert isinstance(rejected, AppException)
    assert rejected.http_status == 403
    with get_sessionmaker()() as db:
        assert db.get(AaTeachingTask, int(facts['oldId'])).teacher_key == new_key
        assert db.get(AaTeachingClassTeacher, relation_id).teacher_key == new_key
        assert not db.query(AaGradeRecord).filter_by(tenant_id=TID, task_id=grade_id).count()


@pytest.mark.parametrize('operation,winner', [
    ('grade_create', 'confirmation'), ('roster_freeze', 'confirmation'),
    ('selection_supply', 'confirmation'), ('grade_create', 'consumer'),
    ('roster_freeze', 'consumer'),
])
def test_formal_handoff_serializes_downstream_creation(client, db_mode, operation, winner):
    """Both orders use actual commands and SQL waits; neither business is forced to a terminal state."""
    import re
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, local
    from sqlalchemy import event
    from app.db.session import get_sessionmaker, get_engine
    from app.models import AaTeachingTask, AaGradeTask, AaSelectionBatch, AaSelectionCourse, AaTeachingTaskSourceHandoff
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grades
    from app.modules.academic_affairs.services import academic_affairs_roster_consumer_service as rosters
    from app.modules.academic_affairs.services import academic_affairs_selection_course_command_service as supply
    from tests.test_aa_task_source_handoff import _setup, _body, _confirm, _context, _task_snapshot

    facts = _setup(client)
    with get_sessionmaker()() as db:
        before = _task_snapshot(db, facts)
        task = db.get(AaTeachingTask, int(facts['newId']))
        course_id = task.course_id
        batch = AaSelectionBatch(tenant_id=TID, term_id=int(facts['termId']),
            batch_name='承接竞争隔离供给批次', status='DRAFT')
        db.add(batch); db.flush()
        selection_batch_id = batch.id
        db.commit()
    body = _body(client, facts)
    held, waiting = Event(), Event()
    worker = local()
    loser = 'consumer' if winner == 'confirmation' else 'confirmation'
    def task_lock(statement):
        return 'FOR UPDATE' in statement.upper() and re.search(r'\bFROM\s+t_aa_teaching_task\b', statement, re.I)
    def after_sql(conn, cursor, statement, parameters, context, executemany):
        if getattr(worker, 'role', None) == winner and not held.is_set() and task_lock(statement):
            held.set()
            assert waiting.wait(10), '另一正式命令未进入共同任务锁等待窗口'
    def before_sql(conn, cursor, statement, parameters, context, executemany):
        # Supply acquires the shared term parent in its archive guard before
        # reaching Task; confirmation already holds that exact parent lock.
        parent_wait = (operation == 'selection_supply' and winner == 'confirmation'
            and 'FOR UPDATE' in statement.upper()
            and re.search(r'\bFROM\s+t_aa_term\b', statement, re.I))
        if getattr(worker, 'role', None) == loser and (task_lock(statement) or parent_wait):
            waiting.set()
    def confirm():
        worker.role = 'confirmation'
        try:
            return _confirm(facts, body)
        except AppException as error:
            return error
    def consume():
        worker.role = 'consumer'
        try:
            with _context(facts['school']) as user:
                if operation == 'grade_create':
                    return grades.create_grade_task(SimpleNamespace(teachingTaskId=facts['newId']), user)
                if operation == 'selection_supply':
                    # Frozen source review admits initial ADMIN_FIXED rosters only.
                    # This checks handoff rejection precedence, not selectable eligibility.
                    return supply.add_course(user, selection_batch_id,
                        SimpleNamespace(teachingTaskId=facts['newId'], courseId=course_id, capacity=30, minCapacity=0))
                with get_sessionmaker()() as db:
                    result = rosters.freeze_consumer_snapshot(db, 'GRADE_TASK', 987654, int(facts['newId']))
                    db.commit()
                    return result
        except AppException as error:
            return error
    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', before_sql)
    event.listen(engine, 'after_cursor_execute', after_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(confirm if winner == 'confirmation' else consume)
            assert held.wait(10), '首个正式命令未取得共同任务锁'
            second = pool.submit(consume if winner == 'confirmation' else confirm)
            first_result, second_result = first.result(timeout=25), second.result(timeout=25)
    finally:
        event.remove(engine, 'before_cursor_execute', before_sql)
        event.remove(engine, 'after_cursor_execute', after_sql)
    assert waiting.is_set()
    assert isinstance(first_result, dict), first_result
    assert isinstance(second_result, AppException), second_result
    assert second_result.http_status == 409
    with get_sessionmaker()() as db:
        relation_count = db.query(AaTeachingTaskSourceHandoff).filter_by(tenant_id=TID, successor_task_id=int(facts['newId'])).count()
        grade_count = db.query(AaGradeTask).filter_by(tenant_id=TID, teaching_task_id=int(facts['newId'])).count()
        roster_count = db.query(AaRosterConsumerSnapshot).filter_by(tenant_id=TID, teaching_task_id=int(facts['newId'])).count()
        supply_count = db.query(AaSelectionCourse).filter_by(tenant_id=TID, teaching_task_id=int(facts['newId'])).count()
        assert _task_snapshot(db, facts) == before
        if winner == 'confirmation':
            assert second_result.details['blocker'] == 'TASK_EXECUTION_HANDOFF'
            assert relation_count == 1
            assert grade_count == roster_count == supply_count == 0
        else:
            assert relation_count == 0
            assert grade_count == (1 if operation == 'grade_create' else 0)
            assert roster_count == (1 if operation == 'roster_freeze' else 0)
            assert supply_count == 0


def test_existing_roster_student_formal_retake_enrollment_blocks_handoff(client, db_mode):
    """The initial roster can stay unchanged while retake enrollment consumes its task."""
    from app.db.session import get_sessionmaker
    from app.models import (StudentProfile, AcademicStudent, AcademicGrade, AaCourse,
        AaTeachingTask, AaTeachingClassRosterVersion, AaRetakeApply, AaTeachingTaskSourceHandoff)
    from app.core.exceptions import AppException
    from tests.test_aa_task_source_handoff import _setup, _body, _confirm
    from tests.test_aa_makeup import _stu_token, _retake_identity

    facts = _setup(client)
    current = client.post(f"{BASE}/terms/{facts['termId']}/set-current", headers=facts['school'])
    assert current.status_code == 200, current.text
    with get_sessionmaker()() as db:
        student = db.get(StudentProfile, 711)
        assert student is not None and student.tenant_id == TID
        academic = AcademicStudent(tenant_id=TID, student_id=student.id,
            student_no=student.student_no, name=student.real_name)
        db.add(academic); db.flush()
        task = db.get(AaTeachingTask, int(facts['newId']))
        course = db.get(AaCourse, task.course_id)
        # Historical failing grade is initial fixture evidence; application,
        # approval and enrollment below must all execute their formal commands.
        grade = AcademicGrade(tenant_id=TID, acad_student_id=academic.id,
            course_id=course.id, course_name=course.course_name, course_code=course.course_code,
            course_version=course.version, attempt_no=1, credit_value=course.credit,
            score=45, pass_status='FAILED', source='PUBLISH', record_status='ACTIVE')
        db.add(grade); db.flush()
        grade_id = grade.id
        student_headers = _stu_token(student.real_name, student.student_no)
        before_versions = db.query(AaTeachingClassRosterVersion).filter_by(tenant_id=TID,
            teaching_class_id=facts['newClassId']).count()
        db.commit()
    body = _body(client, facts)
    applied = client.post(f'{BASE}/retake/apply', headers=student_headers, json={'gradeId': str(grade_id)})
    assert applied.status_code == 200, applied.text
    apply_id = applied.json()['data']['applyId']
    reviewed = client.post(f'{BASE}/retake/applies/{apply_id}/review', headers=facts['school'],
        json={'action': 'APPROVE', **_retake_identity(client, facts['school'], apply_id)})
    assert reviewed.status_code == 200, reviewed.text
    enrolled = client.post(f'{BASE}/retake/applies/{apply_id}/enroll', headers=facts['school'],
        json={'teachingTaskRef': facts['newId'], **_retake_identity(client, facts['school'], apply_id)})
    assert enrolled.status_code == 200, enrolled.text
    assert enrolled.json()['data']['status'] == 'ENROLLED'
    with get_sessionmaker()() as db:
        assert db.query(AaTeachingClassRosterVersion).filter_by(tenant_id=TID,
            teaching_class_id=facts['newClassId']).count() == before_versions
        assert db.get(AaRetakeApply, int(apply_id)).teaching_task_ref == int(facts['newId'])
    with pytest.raises(AppException) as rejected:
        _confirm(facts, body)
    assert rejected.value.http_status == 409
    blockers = rejected.value.details['confirmationBlockers']
    assert any(row['code'] == 'SUCCESSOR_CONSUMPTION' and '重修编班' in row['message'] for row in blockers)
    with get_sessionmaker()() as db:
        assert not db.query(AaTeachingTaskSourceHandoff).filter_by(tenant_id=TID).count()
        assert db.get(AaRetakeApply, int(apply_id)).status == 'ENROLLED'


def _registered_correction_facts(client):
    """Existing published-grade fixture plus complete initial formal teacher identity."""
    from datetime import date
    from app.db.session import get_sessionmaker
    from app.core.security import create_access_token
    from app.services.auth_service_db import _claims, _role_contexts
    from app.models import (AaGradeTask, AaTeachingTask, AaTerm, AaTeachingClassTeacher,
        User)
    from tests.test_aa_grade_correction_command import _seed_published_grade
    from tests.support_academic_review_identity import _ensure_review_account
    from tests.test_aa_schedule import _hdr
    ids = _seed_published_grade()
    teacher_role_code = 'ACADEMIC_TEACHER'
    with get_sessionmaker()() as db:
        grade_task = db.get(AaGradeTask, ids['taskId'])
        task = db.get(AaTeachingTask, grade_task.teaching_task_id)
        teacher = db.get(User, ids['teacherUserId'])
        term = db.get(AaTerm, grade_task.term_id)
        term.start_date, term.end_date, term.teaching_weeks = date(2026, 9, 1), date(2027, 1, 31), 18
        task.start_week, task.end_week, task.teacher_id = 1, 18, teacher.id
        _ensure_review_account(db, login_name=teacher.login_name, real_name=teacher.real_name,
            role_code=teacher_role_code, permissions=('academicAffairs.gradeChange.apply',))
        relation = db.query(AaTeachingClassTeacher).filter_by(tenant_id=TID,
            teaching_class_id=ids['teachingClassId'], role_type='PRIMARY', status='ACTIVE', is_deleted=False).one_or_none()
        if relation is None:
            relation = AaTeachingClassTeacher(tenant_id=TID, teaching_class_id=ids['teachingClassId'],
                teacher_id=teacher.id, teacher_key=teacher.login_name, role_type='PRIMARY',
                start_week=1, end_week=18, status='ACTIVE')
            db.add(relation)
        else:
            relation.start_week, relation.end_week = 1, 18
        replacement = User(tenant_id=TID, login_name='handoff_correction_new_teacher',
            real_name='隔离新教师', password_hash='x', user_type='TEACHER', status='ACTIVE')
        db.add(replacement); db.flush()
        ids.update(relationId=relation.id, replacementKey=replacement.login_name)
        db.commit()
        contexts = _role_contexts(db, teacher)
        teacher_context = next(row for row in contexts if row['roleCode'] == teacher_role_code)
        teacher_headers = {'Authorization': 'Bearer ' + create_access_token(
            _claims(db, teacher, teacher_context, contexts, 'PC'))}
    ids.update(teacherHeaders=teacher_headers, schoolHeaders=_hdr(client, 'school_admin01'),
        collegeHeaders=_hdr(client, 'college_admin01'))
    return ids


def test_registered_correction_preflight_does_not_lock_class_ahead_of_teacher_replacement(client, db_mode, monkeypatch):
    import re
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, local
    from sqlalchemy import event
    from app.db.session import get_sessionmaker, get_engine
    from app.core.exceptions import AppException
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_teacher_service as teachers
    from tests.test_aa_grade_correction_command import _application_body
    from tests.test_aa_task_source_handoff import _context
    ids = _registered_correction_facts(client)
    body = _application_body(ids)
    held, waiting = Event(), Event()
    worker = local()
    original = teachers.update_relation
    def replace(*args, **kwargs):
        worker.role = 'replacement'
        return original(*args, **kwargs)
    def task_lock(statement):
        return 'FOR UPDATE' in statement.upper() and re.search(r'\bFROM\s+t_aa_teaching_task\b', statement, re.I)
    def after_sql(conn, cursor, statement, parameters, context, executemany):
        if getattr(worker, 'role', None) == 'replacement' and not held.is_set() and task_lock(statement):
            held.set()
            assert waiting.wait(10), '更正申请未到共同任务锁等待窗口'
    def before_sql(conn, cursor, statement, parameters, context, executemany):
        if getattr(worker, 'role', None) == 'applicant' and task_lock(statement):
            waiting.set()
    def apply():
        worker.role = 'applicant'
        with _context(ids['teacherHeaders']) as user:
            try:
                # Use the actually registered public service, not a private adapter.
                return grade.change_request(ids['taskId'], ids['recordId'], user, body,
                    command_key='handoff-correction-replacement-race')
            except AppException as error:
                return error
    monkeypatch.setattr(teachers, 'update_relation', replace)
    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', before_sql)
    event.listen(engine, 'after_cursor_execute', after_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            replacement = pool.submit(client.put,
                f"{BASE}/teaching-classes/{ids['teachingClassId']}/teachers/{ids['relationId']}",
                headers=ids['schoolHeaders'], json={'teacherKey': ids['replacementKey'], 'reason': '隔离回归正式更换教师'})
            assert held.wait(10), '正式教师替换未取得共同任务锁'
            applicant = pool.submit(apply)
            response, rejected = replacement.result(timeout=25), applicant.result(timeout=25)
    finally:
        event.remove(engine, 'before_cursor_execute', before_sql)
        event.remove(engine, 'after_cursor_execute', after_sql)
    assert response.status_code == 200, response.text
    assert waiting.is_set()
    assert isinstance(rejected, AppException) and rejected.http_status == 403
    with get_sessionmaker()() as db:
        assert not db.query(AaGradeChangeRequest).filter_by(tenant_id=TID, grade_record_id=ids['recordId']).count()


def test_registered_pending_correction_review_and_duplicate_apply_share_parent_order(client, db_mode):
    import re
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, local
    from sqlalchemy import event
    from app.db.session import get_sessionmaker, get_engine
    from app.core.exceptions import AppException
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    from tests.test_aa_grade_correction_command import _application_body, _review_identity, _record_state
    from tests.test_aa_task_source_handoff import _context
    ids = _registered_correction_facts(client)
    body = _application_body(ids)
    with _context(ids['teacherHeaders']) as user:
        grade.change_request(ids['taskId'], ids['recordId'], user, body,
            command_key='handoff-correction-initial-pending')
    identity, before = _review_identity(ids), _record_state(ids['recordId'])
    held, waiting = Event(), Event()
    worker = local()
    def term_lock(statement):
        return 'FOR UPDATE' in statement.upper() and re.search(r'\bFROM\s+t_aa_term\b', statement, re.I)
    def after_sql(conn, cursor, statement, parameters, context, executemany):
        if getattr(worker, 'role', None) == 'reviewer' and not held.is_set() and term_lock(statement):
            held.set()
            assert waiting.wait(10), '重复申请未进入共同学期锁等待窗口'
    def before_sql(conn, cursor, statement, parameters, context, executemany):
        if getattr(worker, 'role', None) == 'applicant' and term_lock(statement):
            waiting.set()
    def review():
        worker.role = 'reviewer'
        with _context(ids['collegeHeaders']) as user:
            return grade.change_college_review(ids['recordId'], user, 'APPROVE', identity=identity,
                command_key='handoff-correction-pending-review-race')
    def duplicate():
        worker.role = 'applicant'
        with _context(ids['teacherHeaders']) as user:
            try:
                return grade.change_request(ids['taskId'], ids['recordId'], user, body,
                    command_key='handoff-correction-pending-duplicate-race')
            except AppException as error:
                return error
    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', before_sql)
    event.listen(engine, 'after_cursor_execute', after_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reviewer = pool.submit(review)
            assert held.wait(10), '审核未先取得共同学期锁'
            applicant = pool.submit(duplicate)
            reviewed, rejected = reviewer.result(timeout=25), applicant.result(timeout=25)
    finally:
        event.remove(engine, 'before_cursor_execute', before_sql)
        event.remove(engine, 'after_cursor_execute', after_sql)
    assert waiting.is_set()
    assert reviewed['reviewNode'] == 'COLLEGE_REVIEW'
    assert isinstance(rejected, AppException) and rejected.http_status == 409
    assert '在途更正申请' in str(rejected)
    assert _record_state(ids['recordId']) == before
    with get_sessionmaker()() as db:
        request = db.query(AaGradeChangeRequest).filter_by(tenant_id=TID, grade_record_id=ids['recordId']).one()
        assert request.id == identity['changeRequestId']
        assert request.status == 'PENDING' and request.version > identity['expectedRequestVersion']
