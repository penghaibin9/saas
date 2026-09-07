"""The organization inspection must report real references without changing them."""
import importlib
import pytest
from sqlalchemy import select, func
from test_aa_orgs import BASE, TID, _hdr
from test_aa_orgs_tier1_r2 import _seed_scoped
from test_aa_org_read_scope_roundtrip import _class_only


def _check(client, headers, kind, node_id):
    return client.get(f'{BASE}/sync-check/{kind}/{node_id}', headers=headers)


def _refs(report):
    return {r['refType']: r['refCount'] for r in report['refs']}


def test_class_inspection_matches_existing_state_guard_and_keeps_history(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, AffairsAuditTrail
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    checked = _check(client, headers, 'CLASS', ids['c1'])
    assert checked.status_code == 200, checked.text
    result = checked.json()['data']
    preview = client.post(f"{BASE}/classes/{ids['c1']}/state-preview", headers=headers,
                          json={'classStatus': 'DISBANDED', 'expectedVersion': 0}).json()['data']
    assert result['blocked'] and _refs(result)['STUDENT'] == preview['activeStudentCount'] == 2
    assert _refs(result)['TEACHING_TASK'] == preview['openTaskCount']
    empty = _check(client, headers, 'CLASS', ids['cEmpty']).json()['data']
    assert not empty['blocked']
    with get_sessionmaker()() as db:
        assert db.get(SchoolClass, ids['c1']).version == 0
        assert db.get(StudentProfile, ids['s1']).class_id == ids['c1']
        audit = db.scalar(select(AffairsAuditTrail).where(AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == 'AA_ORG_CLASS', AffairsAuditTrail.biz_id == ids['c1'],
            AffairsAuditTrail.action == 'SYNC_CHECK'))
        assert audit and '2' in audit.detail
    assert 'ORG601' not in checked.text and '方向甲' not in checked.text


def test_inspection_counts_unarchived_tasks_and_real_usable_program_states(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, AaTeachingTaskBatch, AaTeachingTask, AaProgram
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        term = AaTerm(tenant_id=TID, year_code='2046-2047', term_no=1, status='DRAFT')
        db.add(term); db.flush()
        batch = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, college_id=ids['colSw'], batch_name='组织引用核对', status='DRAFT')
        db.add(batch); db.flush()
        db.add(AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=9911, class_id=ids['cEmpty'], status='READY'))
        for status in ('PUBLISHED', 'ENABLED', 'FROZEN', 'DISABLED', 'DRAFT'):
            db.add(AaProgram(tenant_id=TID, major_id=ids['majSw'], program_name=f'组织核对方案{status}', status=status))
        db.commit(); term_id = term.id
    response = _check(client, headers, 'MAJOR', ids['majSw'])
    assert response.status_code == 200, response.text
    refs = _refs(response.json()['data'])
    assert refs['PROGRAM'] == 3 and refs['TEACHING_TASK'] == 1 and refs['STUDENT'] == 2
    assert _refs(_check(client, headers, 'CLASS', ids['cEmpty']).json()['data'])['TEACHING_TASK'] == 1
    with get_sessionmaker()() as db:
        db.get(AaTerm, term_id).status = 'ARCHIVED'; db.commit()
    assert _refs(_check(client, headers, 'CLASS', ids['cEmpty']).json()['data'])['TEACHING_TASK'] == 0


def test_inspection_covers_unassigned_students_and_historical_counts(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        db.add_all([
            StudentProfile(tenant_id=TID, student_no='CHECK_UNASSIGNED', real_name='未分班验收', college_id=ids['colSw'],
                major_id=ids['majSw'], student_status='PRESERVED', status='ACTIVE'),
            StudentProfile(tenant_id=TID, student_no='CHECK_HISTORY', real_name='毕业引用验收', college_id=ids['colSw'],
                major_id=ids['majSw'], class_id=ids['cEmpty'], student_status='GRADUATED', status='ACTIVE'),
        ]); db.commit()
    response = _check(client, headers, 'COLLEGE', ids['colSw'])
    assert response.status_code == 200, response.text
    assert _refs(response.json()['data'])['STUDENT'] == 3
    empty = _check(client, headers, 'CLASS', ids['cEmpty']).json()['data']
    assert not empty['blocked'] and empty['historicalStudentCount'] == 1
    assert empty['warnings']  # No false promise that the same class can be deleted.


def test_reference_overview_is_paginated_and_parent_context_is_not_authority(client, db_mode):
    ids = _seed_scoped(db_mode)
    school = _hdr(client, 'school_admin01')
    result = client.get(f'{BASE}/sync-check', headers=school, params={'targetType': 'CLASS', 'collegeId': ids['colSw'], 'pageSize': 2})
    assert result.status_code == 200, result.text
    page = result.json()['data']
    assert page['total'] == 3 and len(page['items']) == 2
    second = client.get(f'{BASE}/sync-check', headers=school, params={'targetType': 'CLASS', 'collegeId': ids['colSw'], 'page': 2, 'pageSize': 2}).json()['data']
    assert len(second['items']) == 1
    assert {r['targetId'] for r in page['items']}.isdisjoint({r['targetId'] for r in second['items']})
    scoped = _hdr(client, 'college_admin01')
    assert _check(client, scoped, 'COLLEGE', ids['colWl']).status_code == 403
    _class_only(ids)
    assert _check(client, scoped, 'CLASS', ids['c1']).status_code == 200
    assert _check(client, scoped, 'CLASS', ids['c2']).status_code == 403
    assert _check(client, scoped, 'COLLEGE', ids['colSw']).status_code == 403
    assert _check(client, scoped, 'MAJOR', ids['majSw']).status_code == 403
    visible = client.get(f'{BASE}/sync-check', headers=scoped).json()['data']['items']
    assert [(r['targetType'], r['targetId']) for r in visible] == [('CLASS', str(ids['c1']))]
    assert _check(client, school, 'CLASS', 999999999).status_code == 404


def test_inspection_audit_failure_does_not_change_organization(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, AffairsAuditTrail
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    svc = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service')
    def fail(*args, **kwargs):
        raise RuntimeError('inspection audit unavailable')
    monkeypatch.setattr(svc, '_audit', fail)
    with pytest.raises(RuntimeError, match='inspection audit unavailable'):
        _check(client, headers, 'CLASS', ids['c1'])
    with get_sessionmaker()() as db:
        assert db.get(SchoolClass, ids['c1']).version == 0
        assert db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == TID, AffairsAuditTrail.action == 'SYNC_CHECK')) == 0
