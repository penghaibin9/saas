"""历史形成方式补证：独立 MySQL 中的正式权限/HTTP 合同，不用于日常沙箱。"""
from concurrent.futures import ThreadPoolExecutor
import hashlib

import pytest

from tests.test_aa_schedule import BASE, TID, _hdr
from tests.test_aa_v5_school_schedule_gate import _facts


def _setup(client):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse, AaTeachingTask, AaTeachingClass, Role, RolePermission, User
    from app.models.file import FileObject
    from tests.support_academic_review_identity import _ensure_permission
    facts = _facts(client)
    with get_sessionmaker()() as db:
        for role_code in ('SCHOOL_ADMIN', 'COLLEGE_ADMIN'):
            role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == role_code).one()
            for code in ('academicAffairs.program.view', 'academicAffairs.program.review'):
                permission = _ensure_permission(db, code)
                if not db.query(RolePermission).filter(RolePermission.tenant_id == TID,
                        RolePermission.role_id == role.id, RolePermission.permission_id == permission.id).first():
                    db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status='ACTIVE'))
        actor = db.query(User).filter(User.tenant_id == TID, User.login_name == 'school_admin01').one()
        task = db.get(AaTeachingTask, int(facts['tasks'][0]['taskId']))
        source = db.get(AaProgramCourse, task.source_program_course_id)
        source.formation_mode = task.formation_mode = None
        clazz = db.query(AaTeachingClass).filter(AaTeachingClass.teaching_task_id == task.id,
            AaTeachingClass.tenant_id == TID).one()
        clazz.class_type = 'ADMIN'
        file = FileObject(tenant_id=TID, file_key='isolated-formation-evidence.pdf',
            file_name='隔离测试原方案审批依据.pdf', owner_user_id=actor.id, visibility='PRIVATE',
            # 对应file_contract.upload_contract：客户端ATTACHMENT也只产生临时私有对象。
            biz_type='TEMP_PRIVATE', biz_id=None,
            status='AVAILABLE', scan_required=False, scan_status='NOT_REQUIRED',
            sha256=hashlib.sha256(b'isolated approved formation evidence').hexdigest())
        db.add(file); db.flush()
        facts.update(sourceId=str(source.id), fileId=str(file.id), actorId=actor.id, classId=clazz.id)
        db.commit()
    facts['school'] = _hdr(client, 'school_admin01')
    facts['college'] = _hdr(client, 'college_admin01')
    return facts


def _url(facts):
    return f"{BASE}/programs/courses/{facts['sourceId']}/formation-proof"


def _body(client, facts):
    response = client.get(_url(facts), headers=facts['school'])
    assert response.status_code == 200, response.text
    return dict(formationMode='ADMIN_FIXED', evidenceFileId=facts['fileId'],
        evidenceLocator='原审批方案课程明细第1行', reason='学校责任人核实原审批材料形成方式',
        expectedSourceFingerprint=response.json()['data']['sourceFingerprint'],
        idempotencyKey='formation-proof-isolated-001')


def test_unknown_has_no_automatic_proof_then_confirm_readback_and_replay(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse, AaTeachingTask, AaProgramCourseFormationProof, AffairsAuditTrail
    facts = _setup(client)
    read = client.get(_url(facts), headers=facts['school']).json()['data']
    assert read['proof'] is None
    assert read['proofValid'] is False
    assert read['originalFormationModeLabel'] == '来源未证明'
    assert read['canConfirm'] is True
    assert all(set(blocker) == {'code', 'message'} for blocker in read['confirmationBlockers'])
    body = _body(client, facts)
    first = client.post(_url(facts), headers=facts['school'], json=body)
    assert first.status_code == 200, first.text
    again = client.post(_url(facts), headers=facts['school'], json=body)
    assert again.status_code == 200, again.text
    assert first.json()['data']['proof']['proofId'] == again.json()['data']['proof']['proofId']
    body['idempotencyKey'] = 'formation-proof-replay-another-key'
    assert client.post(_url(facts), headers=facts['school'], json=body).status_code == 200
    read = client.get(_url(facts), headers=facts['school']).json()['data']
    assert read['proof']['evidence']['fileId'] == facts['fileId']
    evidence = read['proof']['evidence']
    assert evidence['canPreview'] is ('preview' in evidence['allowedActions'])
    assert evidence['canDownload'] is ('download' in evidence['allowedActions'])
    assert set(evidence) == {'fileId', 'fileName', 'ext', 'mimeType', 'sizeBytes',
        'allowedActions', 'canPreview', 'canDownload'}
    assert read['proofValid'] is True
    assert read['proofValidityLabel'] == '有效正式依据'
    assert read['canConfirm'] is False
    with get_sessionmaker()() as db:
        from app.models.file import FileBinding
        assert db.get(AaProgramCourse, int(facts['sourceId'])).formation_mode is None
        assert db.get(AaTeachingTask, int(facts['tasks'][0]['taskId'])).formation_mode is None
        assert db.query(AaProgramCourseFormationProof).filter_by(tenant_id=TID, program_course_id=int(facts['sourceId'])).count() == 1
        assert db.query(AffairsAuditTrail).filter_by(tenant_id=TID, biz_type='AA_PROGRAM_FORMATION_PROOF').count() == 1
        binding = db.query(FileBinding).filter_by(tenant_id=TID, biz_type='AA_PROGRAM_FORMATION_PROOF').one()
        assert binding.subject_type == 'USER'
        assert binding.subject_id == str(facts['actorId'])


@pytest.mark.parametrize('change', ['fingerprint', 'task_mode', 'class_type', 'file_owner', 'file_tenant', 'file_scan', 'file_sha', 'file_unknown_type', 'archived'])
def test_conflict_or_unusable_evidence_cannot_confirm(client, db_mode, change):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingClass, AaProgramCourseFormationProof, AaTerm
    from app.models.file import FileObject
    facts = _setup(client); body = _body(client, facts)
    with get_sessionmaker()() as db:
        file = db.get(FileObject, int(facts['fileId']))
        if change == 'fingerprint': body['expectedSourceFingerprint'] = '0' * 64
        elif change == 'task_mode': db.get(AaTeachingTask, int(facts['tasks'][0]['taskId'])).formation_mode = 'SELECTABLE'
        elif change == 'class_type': db.get(AaTeachingClass, facts['classId']).class_type = 'SELECTIVE'
        elif change == 'file_owner': file.owner_user_id = 999999999
        elif change == 'file_tenant': file.tenant_id = TID + 1
        elif change == 'file_scan': file.scan_required = True; file.scan_status = 'SCANNING'
        elif change == 'file_sha': file.sha256 = None
        elif change == 'file_unknown_type': file.biz_type = 'UNKNOWN_FORMAL_SOURCE'
        elif change == 'archived': db.get(AaTerm, facts['termId']).status = 'ARCHIVED'
        db.commit()
    response = client.post(_url(facts), headers=facts['school'], json=body)
    assert response.status_code in (404, 409), response.text
    with get_sessionmaker()() as db:
        assert db.query(AaProgramCourseFormationProof).filter_by(tenant_id=TID).count() == 0


def test_college_cannot_confirm_and_foreign_source_is_not_visible(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse
    facts = _setup(client); body = _body(client, facts)
    response = client.post(_url(facts), headers=facts['college'], json=body)
    assert response.status_code == 403, response.text
    assert client.get(_url(facts), headers=facts['college']).status_code == 200
    with get_sessionmaker()() as db:
        from app.models import AaTeachingTask
        other = db.get(AaTeachingTask, int(facts['tasks'][1]['taskId'])).source_program_course_id
    outside = dict(facts, sourceId=str(other))
    assert client.get(_url(outside), headers=facts['college']).status_code == 403
    with get_sessionmaker()() as db:
        db.get(AaProgramCourse, int(facts['sourceId'])).tenant_id = TID + 1; db.commit()
    assert client.get(_url(facts), headers=facts['school']).status_code == 404


def test_audit_failure_rolls_back_proof_and_binding(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourseFormationProof
    from app.models.file import FileBinding
    from app.modules.academic_affairs.services import academic_affairs_program_formation_proof_service as service
    facts = _setup(client); body = _body(client, facts)
    def fail(*args, **kwargs):
        raise RuntimeError('isolated audit failure')
    monkeypatch.setattr(service, '_write_audit', fail)
    try:
        response = client.post(_url(facts), headers=facts['school'], json=body)
        assert response.status_code >= 500, response.text
    except RuntimeError as error:
        assert 'isolated audit failure' in str(error)
    with get_sessionmaker()() as db:
        assert db.query(AaProgramCourseFormationProof).filter_by(tenant_id=TID).count() == 0
        assert db.query(FileBinding).filter_by(tenant_id=TID, biz_type='AA_PROGRAM_FORMATION_PROOF').count() == 0


def test_concurrent_same_source_different_payload_cannot_both_confirm(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourseFormationProof
    facts = _setup(client); body = _body(client, facts)
    second = dict(body, reason='另一份责任核实说明不得覆盖首次证据', idempotencyKey='formation-proof-competing-key')
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda payload: client.post(_url(facts), headers=facts['school'], json=payload), [body, second]))
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    with get_sessionmaker()() as db:
        assert db.query(AaProgramCourseFormationProof).filter_by(tenant_id=TID).count() == 1


def test_confirmed_proof_cannot_be_overwritten_or_reuse_key_for_other_source(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse, AaTeachingTask
    facts = _setup(client); body = _body(client, facts)
    assert client.post(_url(facts), headers=facts['school'], json=body).status_code == 200
    changed = dict(body, reason='另一种确认说明不能静默覆盖')
    assert client.post(_url(facts), headers=facts['school'], json=changed).status_code == 409
    with get_sessionmaker()() as db:
        task = db.get(AaTeachingTask, int(facts['tasks'][1]['taskId']))
        source = db.get(AaProgramCourse, task.source_program_course_id)
        source.formation_mode = task.formation_mode = None
        other_id = str(source.id); db.commit()
    other = dict(facts, sourceId=other_id)
    other_body = _body(client, other)
    assert client.post(_url(other), headers=facts['school'], json=other_body).status_code == 409


def test_role_name_without_active_school_responsibility_cannot_confirm(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import StaffAssignment
    facts = _setup(client); body = _body(client, facts)
    with get_sessionmaker()() as db:
        assignments = db.query(StaffAssignment).filter_by(tenant_id=TID, user_id=facts['actorId'],
            org_type='SCHOOL', assignment_type='ACADEMIC_REVIEWER').all()
        for assignment in assignments:
            assignment.status = 'INACTIVE'
        db.commit()
    response = client.post(_url(facts), headers=facts['school'], json=body)
    assert response.status_code == 403, response.text


def test_proof_readback_never_exposes_inaccessible_or_changed_evidence(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models.file import FileObject, FileBinding
    facts = _setup(client); body = _body(client, facts)
    assert client.post(_url(facts), headers=facts['school'], json=body).status_code == 200
    with get_sessionmaker()() as db:
        file = db.get(FileObject, int(facts['fileId']))
        file.sha256 = '0' * 64; db.commit()
    data = client.get(_url(facts), headers=facts['school']).json()['data']
    assert data['proof']['evidence'] is None
    assert data['proofValid'] is False
    with get_sessionmaker()() as db:
        file = db.get(FileObject, int(facts['fileId']))
        file.sha256 = hashlib.sha256(b'isolated approved formation evidence').hexdigest()
        file.owner_user_id = 999999999
        for binding in db.query(FileBinding).filter_by(tenant_id=TID, file_id=file.id).all():
            binding.status = 'INACTIVE'
        db.commit()
    data = client.get(_url(facts), headers=facts['school']).json()['data']
    assert data['proof']['evidence'] is None
    assert data['proofValid'] is True
    assert data['proofValidityLabel'] == '有效正式依据'


@pytest.mark.parametrize('change,code', [
    ('source', 'FORMATION_PROOF_SOURCE_CHANGED'),
    ('version', 'FORMATION_PROOF_SOURCE_CHANGED'),
    ('file_hash', 'FORMATION_PROOF_EVIDENCE_UNAVAILABLE'),
    ('file_scan', 'FORMATION_PROOF_EVIDENCE_UNAVAILABLE'),
    ('proof_payload', 'FORMATION_PROOF_PAYLOAD_CHANGED'),
])
def test_get_matches_canonical_invalidity_without_hiding_history_or_allowing_overwrite(client, db_mode, change, code):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramCourse, AaProgramCourseFormationProof
    from app.models.file import FileObject
    facts = _setup(client); body = _body(client, facts)
    created = client.post(_url(facts), headers=facts['school'], json=body)
    assert created.status_code == 200, created.text
    proof_id = created.json()['data']['proof']['proofId']
    with get_sessionmaker()() as db:
        source = db.get(AaProgramCourse, int(facts['sourceId']))
        proof = db.get(AaProgramCourseFormationProof, int(proof_id))
        file = db.get(FileObject, int(facts['fileId']))
        if change == 'source': source.credit_snapshot += 1
        elif change == 'version': db.get(AaProgram, source.program_id).version += 1
        elif change == 'file_hash': file.sha256 = '0' * 64
        elif change == 'file_scan': file.scan_required = True; file.scan_status = 'SCANNING'
        elif change == 'proof_payload': proof.payload_hash = '0' * 64
        db.commit()
    response = client.get(_url(facts), headers=facts['school'])
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['proofValid'] is False
    assert data['proofValidityLabel'] == '既有确认已失效'
    assert data['formationModeLabel'] == '既有确认已失效，需核对来源依据'
    assert data['canConfirm'] is False
    assert any(blocker['code'] == code for blocker in data['confirmationBlockers'])
    assert data['proof']['proofId'] == proof_id
    assert data['proof']['reason'] == body['reason']
    assert data['proof']['evidenceLocator'] == body['evidenceLocator']
    with get_sessionmaker()() as db:
        assert db.query(AaProgramCourseFormationProof).filter_by(tenant_id=TID,
            program_course_id=int(facts['sourceId'])).count() == 1


def test_proof_and_school_batch_approval_share_batch_before_task_lock_order(client, db_mode, monkeypatch):
    """保留真实服务/DB/权限：仅用事件在批次已锁、任务未锁处排列并发窗口。"""
    from threading import Event, local
    from sqlalchemy import event
    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaProgramCourseFormationProof
    from app.modules.academic_affairs.services import academic_affairs_task_service as task_service
    from app.modules.academic_affairs.services import academic_affairs_program_formation_proof_service as proof_service
    facts = _setup(client); body = _body(client, facts)
    with get_sessionmaker()() as db:
        task = db.get(AaTeachingTask, int(facts['tasks'][0]['taskId']))
        task.status = 'TEACHER_CONFIRMED'
        batch = db.get(AaTeachingTaskBatch, task.batch_id)
        batch.status = 'COLLEGE_CONFIRMED'
        batch.editable_scope_key = None
        batch_id = task.batch_id; db.commit()
    batch_locked, proof_entered = Event(), Event()
    proof_thread = local()
    original_ready = task_service._require_batch_ready
    original_impact = proof_service._impact
    def ready(db, selected_batch):
        if selected_batch == batch_id:
            batch_locked.set()
            assert proof_entered.wait(10), '补证请求未进入关联锁核对'
        return original_ready(db, selected_batch)
    def impact(db, source, mode=None, **kwargs):
        proof_thread.active = bool(kwargs.get('lock'))
        try:
            return original_impact(db, source, mode, **kwargs)
        finally:
            proof_thread.active = False
    def before_execute(conn, cursor, statement, parameters, context, executemany):
        if (getattr(proof_thread, 'active', False) and 't_aa_teaching_task_batch' in statement
                and 'FOR UPDATE' in statement.upper()):
            proof_entered.set()
    monkeypatch.setattr(task_service, '_require_batch_ready', ready)
    monkeypatch.setattr(proof_service, '_impact', impact)
    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', before_execute)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            approval = pool.submit(client.post, f'{BASE}/teaching-task-batches/{batch_id}/review',
                headers=facts['school'], json={'action': 'APPROVE'})
            assert batch_locked.wait(10), '学校终审未取得批次锁'
            confirmation = pool.submit(client.post, _url(facts), headers=facts['school'], json=body)
            responses = [approval.result(timeout=25), confirmation.result(timeout=25)]
    finally:
        event.remove(engine, 'before_cursor_execute', before_execute)
    assert [response.status_code for response in responses] == [200, 200], [r.text for r in responses]
    with get_sessionmaker()() as db:
        assert db.get(AaTeachingTaskBatch, batch_id).status == 'APPROVED'
        assert db.get(AaTeachingTask, int(facts['tasks'][0]['taskId'])).status == 'READY'
        assert db.query(AaProgramCourseFormationProof).filter_by(tenant_id=TID,
            program_course_id=int(facts['sourceId'])).count() == 1
