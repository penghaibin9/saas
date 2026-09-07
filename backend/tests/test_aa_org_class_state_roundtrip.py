"""Class editor lifecycle checks use the same references as batch adjustments."""
import importlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import func, select
from test_aa_orgs import BASE, TID, _hdr
from test_aa_orgs_tier1_r2 import _seed_scoped


def _preview(client, headers, cid, target='DISBANDED', **extra):
    return client.post(f'{BASE}/classes/{cid}/state-preview', headers=headers,
                       json={'classStatus': target, **extra})


def _save(client, headers, cid, **extra):
    return client.put(f'{BASE}/classes/{cid}', headers=headers,
                      json={'classStatus': 'DISBANDED', 'reason': '行政班状态真实闭环验收', **extra})


def _delete(client, headers, cid):
    return client.delete(f'{BASE}/classes/{cid}', headers=headers)


def test_direct_state_edit_cannot_close_a_class_with_students(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    for body in ({'classStatus': 'DISBANDED'}, {'classStatus': 'GRADUATED'}, {'classStatus': 'NORMAL', 'status': 'INACTIVE'}):
        response = _save(client, headers, ids['c1'], **body)
        assert response.status_code == 400, response.text
        assert '学生' in response.json()['message']
    checked = _preview(client, headers, ids['c1'])
    assert checked.status_code == 200, checked.text
    assert checked.json()['data']['blocked'] and checked.json()['data']['activeStudentCount'] == 2
    with get_sessionmaker()() as db:
        row = db.get(SchoolClass, ids['c1'])
        assert (row.class_status, row.status, row.version) == ('NORMAL', 'ACTIVE', 0)


def test_state_edit_and_delete_cannot_hide_unarchived_teaching_tasks(client, db_mode, monkeypatch):
    from app.core.exceptions import AppException
    from app.services import org_master_service as master
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, AaTeachingTaskBatch, AaTeachingTask, SchoolClass
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        term = AaTerm(tenant_id=TID, year_code='2044-2045', term_no=1, status='DRAFT')
        db.add(term); db.flush()
        batch = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name='状态核对验收', status='DRAFT')
        db.add(batch); db.flush()
        db.add(AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=9944, class_id=ids['cEmpty'], status='READY'))
        db.commit(); term_id = term.id
    assert _save(client, headers, ids['cEmpty']).status_code == 400
    deleted = client.delete(f"{BASE}/classes/{ids['cEmpty']}", headers=headers)
    assert deleted.status_code == 409, deleted.text
    monkeypatch.setattr(master, '_tid', lambda: TID)
    with pytest.raises(AppException, match='未归档教学任务'):
        master.disable_org_node(node_type='CLASS', node_id=ids['cEmpty'], reason='引用保护核对验收')
    checked = _preview(client, headers, ids['cEmpty']).json()['data']
    assert checked['blocked'] and checked['openTaskCount'] == 1
    with get_sessionmaker()() as db:
        assert not db.get(SchoolClass, ids['cEmpty']).is_deleted
        db.get(AaTerm, term_id).status = 'ARCHIVED'
        db.commit()
    checked = _preview(client, headers, ids['cEmpty']).json()['data']
    assert not checked['blocked'] and checked['openTaskCount'] == 0
    assert _save(client, headers, ids['cEmpty'], expectedStateSnapshotHash=checked['snapshotHash']).status_code == 200
    assert _delete(client, headers, ids['cEmpty']).status_code == 200
    with get_sessionmaker()() as db:
        row = db.get(SchoolClass, ids['cEmpty'])
        assert row.is_deleted and row.version == 2


def test_preview_is_readonly_and_save_preserves_terminal_student_facts(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, StudentAcademicFact, AffairsAuditTrail
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        student = StudentProfile(tenant_id=TID, student_no='CLASS_CLOSED_01', real_name='已离校验收学生',
            class_id=ids['cEmpty'], major_id=ids['majSw'], college_id=ids['colSw'], student_status='GRADUATED', status='ACTIVE')
        db.add(student); db.commit(); sid = student.id
        before_audit = db.scalar(select(func.count()).select_from(AffairsAuditTrail))
    checked_response = _preview(client, headers, ids['cEmpty'], 'GRADUATED', expectedVersion=0)
    assert checked_response.status_code == 200, checked_response.text
    checked = checked_response.json()['data']
    assert not checked['blocked'] and checked['activeStudentCount'] == 0
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(AffairsAuditTrail)) == before_audit
        assert db.get(SchoolClass, ids['cEmpty']).version == 0
    response = _save(client, headers, ids['cEmpty'], classStatus='GRADUATED', expectedVersion=0,
                     expectedStateSnapshotHash=checked['snapshotHash'], className='毕业结班验收名称')
    assert response.status_code == 200, response.text
    assert response.json()['data']['version'] == 1
    with get_sessionmaker()() as db:
        assert db.get(StudentProfile, sid).student_status == 'GRADUATED'
        assert db.scalar(select(func.count()).select_from(StudentAcademicFact).where(StudentAcademicFact.student_id == sid)) == 1
        audit = db.scalars(select(AffairsAuditTrail).where(AffairsAuditTrail.biz_type == 'AA_ORG_CLASS',
            AffairsAuditTrail.biz_id == ids['cEmpty'], AffairsAuditTrail.action == 'UPDATE')).one()
        assert '行政班状态真实闭环验收' in audit.detail


def test_a_new_member_after_preview_invalidates_the_entire_edit(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    checked_response = _preview(client, headers, ids['cEmpty'])
    assert checked_response.status_code == 200, checked_response.text
    checked = checked_response.json()['data']
    with get_sessionmaker()() as db:
        original_name = db.get(SchoolClass, ids['cEmpty']).class_name
        db.add(StudentProfile(tenant_id=TID, student_no='CLASS_LATE_01', real_name='核对后入班', class_id=ids['cEmpty'],
            major_id=ids['majSw'], college_id=ids['colSw'], student_status='PRESERVED', status='ACTIVE'))
        db.commit()
    response = _save(client, headers, ids['cEmpty'], expectedStateSnapshotHash=checked['snapshotHash'], className='不应保存的新名称')
    assert response.status_code == 409, response.text
    with get_sessionmaker()() as db:
        assert db.get(SchoolClass, ids['cEmpty']).class_name == original_name
        assert db.get(SchoolClass, ids['cEmpty']).class_status == 'NORMAL'


def test_business_audit_failure_rolls_back_master_data_and_scope_rename(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, TeacherStudentScope
    svc = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service')
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        original_name = db.get(SchoolClass, ids['c1']).class_name
        scope = TeacherStudentScope(tenant_id=TID, teacher_key='state_rollback_teacher', teacher_name='验收教师',
            role_code='COUNSELOR', scope_type='CLASS', ref_value=original_name, status='ACTIVE')
        db.add(scope); db.commit(); scope_id = scope.id
    def fail(*args, **kwargs):
        raise RuntimeError('class audit failure')
    monkeypatch.setattr(svc, '_audit', fail)
    with pytest.raises(RuntimeError, match='class audit failure'):
        client.put(f"{BASE}/classes/{ids['c1']}", headers=headers, json={'className': '事务失败的新名称', 'expectedVersion': 0})
    with get_sessionmaker()() as db:
        assert db.get(SchoolClass, ids['c1']).class_name == original_name
        assert db.get(SchoolClass, ids['c1']).version == 0
        assert db.get(TeacherStudentScope, scope_id).ref_value == original_name


def test_state_preview_keeps_scope_and_reason_guards(client, db_mode):
    ids = _seed_scoped(db_mode)
    college = _hdr(client, 'college_admin01')
    assert _preview(client, college, ids['cWl']).status_code == 403
    school = _hdr(client, 'school_admin01')
    assert _preview(client, school, 99999999).status_code == 404
    assert _preview(client, school, ids['cEmpty'], 'UNKNOWN').status_code in (400, 422)
    assert _save(client, school, ids['cEmpty'], reason='').status_code == 400
    assert _save(client, school, ids['cEmpty'], reason='   ').status_code == 400
    assert _save(client, school, ids['cEmpty'], expectedVersion=900).status_code == 409


def test_concurrent_class_edits_have_one_version_and_one_atomic_audit(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, AffairsAuditTrail, SecurityAuditLog
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    barrier = Barrier(2)
    def save(label):
        barrier.wait(timeout=10)
        return client.put(f"{BASE}/classes/{ids['cEmpty']}", headers=headers,
                          json={'className': label, 'expectedVersion': 0})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(save, name) for name in ('并发名称甲', '并发名称乙')]
        responses = [future.result(timeout=30) for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409], [response.text for response in responses]
    with get_sessionmaker()() as db:
        assert db.get(SchoolClass, ids['cEmpty']).version == 1
        assert db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == TID, AffairsAuditTrail.biz_type == 'AA_ORG_CLASS', AffairsAuditTrail.biz_id == ids['cEmpty'])) == 1
        assert db.scalar(select(func.count()).select_from(SecurityAuditLog).where(SecurityAuditLog.tenant_id == TID,
            SecurityAuditLog.action == 'ORG_NODE_SAVE', SecurityAuditLog.resource == f"CLASS:{ids['cEmpty']}")) == 1


def test_state_checks_revalidate_scope_after_parent_moves(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import Major, SchoolClass
    svc = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service')
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'college_admin01')
    original = svc._class_college_id
    def move_parent_after_initial_scope_read(db, cid):
        college_id = original(db, cid)
        with get_sessionmaker()() as other:
            other.get(Major, ids['majSw']).college_id = ids['colWl']
            other.commit()
        return college_id
    monkeypatch.setattr(svc, '_class_college_id', move_parent_after_initial_scope_read)
    for action in (_preview, _save, _delete):
        response = action(client, headers, ids['cEmpty'])
        assert response.status_code == 403, response.text
        with get_sessionmaker()() as db:
            assert db.get(SchoolClass, ids['cEmpty']).class_status == 'NORMAL'
            db.get(Major, ids['majSw']).college_id = ids['colSw']
            db.commit()


def test_shared_master_adapter_also_rejects_closing_referenced_classes(db_mode, monkeypatch):
    from app.core.exceptions import AppException
    from app.services import org_master_service as master
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    ids = _seed_scoped(db_mode)
    monkeypatch.setattr(master, '_tid', lambda: TID)
    with pytest.raises(AppException, match='在籍学生'):
        master.save_org_node(node_type='CLASS', node_id=ids['c1'], name='软件2601', expected_version=0,
                             extras={'class_status': 'DISBANDED'})
    with get_sessionmaker()() as db:
        assert db.get(SchoolClass, ids['c1']).class_status == 'NORMAL'
        assert db.get(SchoolClass, ids['c1']).version == 0


def test_delete_audit_failure_rolls_back_class_and_master_audit(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, SecurityAuditLog
    svc = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service')
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    def fail(*args, **kwargs):
        raise RuntimeError('delete audit failure')
    monkeypatch.setattr(svc, '_audit', fail)
    with pytest.raises(RuntimeError, match='delete audit failure'):
        _delete(client, headers, ids['cEmpty'])
    with get_sessionmaker()() as db:
        row = db.get(SchoolClass, ids['cEmpty'])
        assert not row.is_deleted and row.version == 0 and row.class_status == 'NORMAL'
        assert db.scalar(select(func.count()).select_from(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == TID, SecurityAuditLog.action == 'ORG_NODE_DELETE',
            SecurityAuditLog.resource == f"CLASS:{ids['cEmpty']}")) == 0
