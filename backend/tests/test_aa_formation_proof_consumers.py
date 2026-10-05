"""Formal confirmation supplies read-only authority to existing consumers."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest

from tests.test_aa_program_formation_proof import _setup, _body, _url
from tests.test_aa_schedule import TID


@contextmanager
def _tenant_scope():
    from app.core.context import get_tenant, set_tenant
    previous = get_tenant()
    set_tenant(TID)
    try:
        yield
    finally:
        set_tenant(previous)


def _confirm(client):
    facts = _setup(client)
    response = client.post(_url(facts), headers=facts['school'], json=_body(client, facts))
    assert response.status_code == 200, response.text
    return facts


def test_confirmed_evidence_is_shared_without_backfilling_original_fields(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse, AaTeachingTask
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as authority
    from app.modules.academic_affairs.services import academic_affairs_task_generation_service as generation
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as classes
    facts = _confirm(client)
    with get_sessionmaker()() as db, _tenant_scope():
        source = db.get(AaProgramCourse, int(facts['sourceId']))
        task_id = int(facts['tasks'][0]['taskId'])
        snapshot = authority.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)
        assert snapshot['status'] == 'PROVEN'
        assert snapshot['formationMode'] == 'ADMIN_FIXED'
        assert snapshot['proofOrigin'] == 'HISTORICAL_CONFIRMATION'
        assert generation._snapshot_program_course_formation(source, db=db) == 'ADMIN_FIXED'
        teaching_class = classes.ensure_teaching_class_for_task(db, task_id)
        assert teaching_class.class_type == 'ADMIN'
        assert json.loads(teaching_class.source_snapshot_json)['formationMode'] == 'ADMIN_FIXED'
        assert source.formation_mode is None
        assert db.get(AaTeachingTask, task_id).formation_mode is None


@pytest.mark.parametrize('changed', ['credit', 'version', 'proof_mode', 'file_hash', 'file_tenant', 'file_deleted', 'file_scan'])
def test_evidence_drift_cannot_authorize_generation_or_projection(client, db_mode, changed):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse, AaProgram, AaProgramCourseFormationProof
    from app.models.file import FileObject
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as authority
    from app.modules.academic_affairs.services import academic_affairs_task_generation_service as generation
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as classes
    facts = _confirm(client)
    with get_sessionmaker()() as db:
        source = db.get(AaProgramCourse, int(facts['sourceId']))
        file = db.get(FileObject, int(facts['fileId']))
        if changed == 'credit': source.credit_snapshot = 3
        elif changed == 'version': db.get(AaProgram, source.program_id).version += 1
        elif changed == 'proof_mode':
            db.query(AaProgramCourseFormationProof).filter_by(tenant_id=TID, program_course_id=source.id).one().formation_mode = 'SELECTABLE'
        elif changed == 'file_hash': file.sha256 = '0' * 64
        elif changed == 'file_tenant': file.tenant_id = TID + 1
        elif changed == 'file_deleted': file.is_deleted = True
        elif changed == 'file_scan': file.scan_status = 'SCANNING'
        db.commit()
    with get_sessionmaker()() as db, _tenant_scope():
        source = db.get(AaProgramCourse, int(facts['sourceId']))
        task_id = int(facts['tasks'][0]['taskId'])
        assert authority.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)['status'] == 'CONFLICT'
        with pytest.raises(AppException) as conflict:
            generation._snapshot_program_course_formation(source, db=db)
        assert conflict.value.http_status == 409
        with pytest.raises(AppException) as conflict:
            classes.ensure_teaching_class_for_task(db, task_id)
        assert conflict.value.http_status == 409


def test_batch_authority_uses_one_tenant_scoped_query(client, db_mode):
    from app.db.session import get_sessionmaker, get_engine
    from app.models import AaProgramCourse
    from sqlalchemy import event
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as authority
    facts = _confirm(client)
    with get_sessionmaker()() as db:
        sources = db.query(AaProgramCourse).filter_by(tenant_id=TID).all()
        queries = []
        def count(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)
        engine = get_engine()
        event.listen(engine, 'before_cursor_execute', count)
        try:
            snapshots = authority.resolve_program_course_formation_snapshots(db, sources, tenant_id=TID)
        finally:
            event.remove(engine, 'before_cursor_execute', count)
        assert len(queries) == 1
        assert snapshots[int(facts['sourceId'])]['proofOrigin'] == 'HISTORICAL_CONFIRMATION'


def _untasked_generation_facts(client):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaProgram, AaProgramBinding, AaProgramCourse, AaTeachingTask, AaTeachingClass, SchoolClass
    facts = _setup(client)
    with get_sessionmaker()() as db:
        old_source = db.get(AaProgramCourse, int(facts['sourceId']))
        program = db.get(AaProgram, old_source.program_id)
        # School-schedule fixtures omit catalog quality; generation must pass the real precheck.
        program.total_credits = 2
        old_source.module = 'MAJOR_CORE'
        db.get(AaCourse, old_source.course_id).status = 'ENABLED'
        old_task = db.get(AaTeachingTask, int(facts['tasks'][0]['taskId']))
        old_class = db.get(SchoolClass, old_task.class_id)
        new_class = SchoolClass(tenant_id=TID, major_id=program.major_id,
            grade=old_class.grade, class_name='补证生成并发隔离班', class_status='NORMAL', status='ACTIVE')
        course = AaCourse(tenant_id=TID, course_code='PROOF-CONCURRENT', course_name='补证生成并发隔离课程',
            owner_college_id=int(facts['tasks'][0]['collegeId']), credit=1, hours_total=36,
            category='MAJOR_CORE', status='ENABLED')
        db.add_all([new_class, course]); db.flush()
        source = AaProgramCourse(tenant_id=TID, program_id=program.id, course_id=course.id,
            course_name=course.course_name, open_term_no=old_source.open_term_no,
            module='MAJOR_CORE', credit_snapshot=1, formation_mode=None)
        db.add(source)
        db.add(AaProgramBinding(tenant_id=TID, program_id=program.id, major_id=program.major_id,
            grade_year=program.grade_year, class_id=new_class.id, bound_at=datetime(2041, 8, 1), status='ACTIVE'))
        db.flush()
        new_facts = dict(facts, sourceId=str(source.id), targetClassId=str(new_class.id), targetCourseId=str(course.id))
        class_id, course_id, program_id = new_class.id, course.id, program.id
        db.commit()
    from tests.support_program_quality_fixture import seed_program_quality_requirements
    seed_program_quality_requirements(program_id, total_credits=2, module='MAJOR_CORE')
    return new_facts


def test_confirmed_selectable_source_generates_selection_without_rewriting_source(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse, AaTeachingTask, AaTeachingClass
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as authority
    from tests.test_aa_schedule import BASE
    facts = _untasked_generation_facts(client)
    confirmed = client.post(_url(facts), headers=facts['school'], json=dict(_body(client, facts), formationMode='SELECTABLE'))
    assert confirmed.status_code == 200, confirmed.text
    generated = client.post(f'{BASE}/teaching-task-batches/generate', headers=facts['school'],
        json={'termId': str(facts['termId']), 'collegeId': facts['tasks'][0]['collegeId'], 'classId': facts['targetClassId']})
    assert generated.status_code == 200, generated.text
    with get_sessionmaker()() as db:
        task = db.query(AaTeachingTask).filter_by(tenant_id=TID,
            course_id=int(facts['targetCourseId']), class_id=int(facts['targetClassId'])).one()
        clazz = db.query(AaTeachingClass).filter_by(tenant_id=TID, teaching_task_id=task.id).one()
        snapshot = authority.resolve_task_formation_snapshot(db, task.id, tenant_id=TID)
        assert task.formation_mode == snapshot['formationMode'] == 'SELECTABLE'
        assert snapshot['status'] == 'PROVEN'
        assert snapshot['proofOrigin'] == 'HISTORICAL_CONFIRMATION'
        assert clazz.class_type == 'SELECTION'
        assert db.get(AaProgramCourse, int(facts['sourceId'])).formation_mode is None


def test_untasked_source_confirmation_and_generation_share_program_lock(client, db_mode, monkeypatch):
    """A real SQL interleave must reject evidence contradicting the committed ADMIN projection."""
    from threading import Event, local
    from sqlalchemy import event
    from app.db.session import get_sessionmaker, get_engine
    from app.models import AaProgramCourse, AaProgramCourseFormationProof, AaTeachingTask, AaTeachingClass
    from app.modules.academic_affairs.services import academic_affairs_task_service as generation_command
    from app.modules.academic_affairs.services import academic_affairs_program_formation_proof_service as proof
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as authority
    from tests.test_aa_schedule import BASE
    facts = _untasked_generation_facts(client)
    body = dict(_body(client, facts), formationMode='SELECTABLE')
    prepared, proof_attempted, proof_finished = Event(), Event(), Event()
    worker = local()
    original_generation, original_proof = generation_command.generate_batch, proof.confirm_formation_proof
    def generating(*args, **kwargs):
        worker.role = 'generation'
        try:
            return original_generation(*args, **kwargs)
        finally:
            worker.role = None
    def confirming(*args, **kwargs):
        worker.role = 'proof'
        try:
            return original_proof(*args, **kwargs)
        finally:
            proof_finished.set(); worker.role = None
    def interleave(conn, cursor, statement, parameters, context, executemany):
        if (getattr(worker, 'role', None) == 'generation' and not prepared.is_set()
            and statement.lower().startswith('insert into t_aa_teaching_task (')):
            prepared.set()
            assert proof_attempted.wait(10), '确认请求未到达共同方案锁'
            # With the common lock, confirmation cannot complete until this generation commits.
            # An older unlocked generator would allow it to finish and then write a stale ADMIN projection.
            proof_finished.wait(1)
        if (getattr(worker, 'role', None) == 'proof' and 'FOR UPDATE' in statement.upper()
            and re.search(r'\bFROM\s+t_aa_program\b', statement, re.I)):
            proof_attempted.set()
    monkeypatch.setattr(generation_command, 'generate_batch', generating)
    monkeypatch.setattr(proof, 'confirm_formation_proof', confirming)
    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', interleave)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            generated = pool.submit(client.post, f'{BASE}/teaching-task-batches/generate', headers=facts['school'],
                json={'termId': str(facts['termId']), 'collegeId': str(facts['tasks'][0]['collegeId']), 'classId': facts['targetClassId']})
            if not prepared.wait(10):
                if generated.done():
                    response = generated.result()
                    pytest.fail(f'正式生成在新增任务前返回：{response.status_code} {response.text}')
                pytest.fail('正式生成未进入新增任务窗口')
            confirmed = pool.submit(client.post, _url(facts), headers=facts['school'], json=body)
            generation_result, confirmation_result = generated.result(timeout=25), confirmed.result(timeout=25)
    finally:
        event.remove(engine, 'before_cursor_execute', interleave)
    assert generation_result.status_code == 200, generation_result.text
    assert confirmation_result.status_code == 409, confirmation_result.text
    with get_sessionmaker()() as db:
        task = db.query(AaTeachingTask).filter_by(tenant_id=TID,
            course_id=int(facts['targetCourseId']), class_id=int(facts['targetClassId'])).one()
        clazz = db.query(AaTeachingClass).filter_by(tenant_id=TID, teaching_task_id=task.id).one()
        snapshot = authority.resolve_task_formation_snapshot(db, task.id, tenant_id=TID)
        assert snapshot['status'] == 'UNKNOWN'
        assert clazz.class_type == 'ADMIN'
        assert db.get(AaProgramCourse, int(facts['sourceId'])).formation_mode is None
        assert not db.query(AaProgramCourseFormationProof).filter_by(tenant_id=TID,
            program_course_id=int(facts['sourceId'])).count()
