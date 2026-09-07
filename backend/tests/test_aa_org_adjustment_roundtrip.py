"""Organization adjustment precheck, execution and transaction boundary tests on real MySQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

from sqlalchemy import func, select

from test_aa_orgs import BASE, TID, _hdr
from test_aa_orgs_tier1_r2 import _seed_scoped


def _create(client, headers, sources, kind='DISBAND', target=None):
    response = client.post(f'{BASE}/class-adjustment-requests', headers=headers, json={
        'adjustType': kind, 'fromClassIds': [str(value) for value in sources],
        'toClassId': str(target) if target else None, 'reason': '独立组织调整闭环验收',
    })
    assert response.status_code == 200, response.text
    return response.json()['data']


def _act(client, headers, row, action, **body):
    return client.post(f"{BASE}/class-adjustment-requests/{row['id']}/{action}", headers=headers, json=body)


def test_merge_cannot_disable_a_source_with_active_students(client, db_mode):
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    row = _create(client, headers, [ids['c1']], 'MERGE', ids['c2'])
    checked = _act(client, headers, row, 'precheck').json()['data']
    assert checked['checkResult']['blocked'] is True
    assert checked['checkResult']['refs'][0]['activeStudentCount'] == 2
    assert _act(client, headers, row, 'execute').status_code == 400


def test_execution_rechecks_new_students_and_preserves_class_and_request(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, AaClassAdjustmentRequest
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    row = _create(client, headers, [ids['cEmpty']])
    assert not _act(client, headers, row, 'precheck').json()['data']['checkResult']['blocked']
    with get_sessionmaker()() as db:
        db.add(StudentProfile(tenant_id=TID, student_no='AFTER_CHECK', real_name='核对后入班学生',
            class_id=ids['cEmpty'], major_id=ids['majSw'], college_id=ids['colSw'],
            student_status='PRESERVED', current_stage='ON_CAMPUS', status='ACTIVE'))
        db.commit()
    response = _act(client, headers, row, 'execute')
    assert response.status_code == 409, response.text
    with get_sessionmaker()() as db:
        assert db.get(SchoolClass, ids['cEmpty']).class_status == 'NORMAL'
        assert db.get(AaClassAdjustmentRequest, int(row['id'])).status == 'CHECKED'
    assert _act(client, headers, row, 'precheck').json()['data']['checkResult']['blocked']
    assert _act(client, headers, row, 'cancel').status_code == 200


def test_changed_class_requires_recheck_and_execution_increments_master_version(client, db_mode):
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    row = _create(client, headers, [ids['cEmpty']])
    _act(client, headers, row, 'precheck')
    update = client.put(f"{BASE}/classes/{ids['cEmpty']}", headers=headers,
                        json={'className': '核对后改名的空班'}).json()['data']
    response = _act(client, headers, row, 'execute')
    assert response.status_code == 409, response.text
    _act(client, headers, row, 'precheck')
    done = _act(client, headers, row, 'execute')
    assert done.status_code == 200, done.text
    stale = client.put(f"{BASE}/classes/{ids['cEmpty']}", headers=headers,
        json={'classStatus': 'NORMAL', 'expectedVersion': update['version']})
    assert stale.status_code == 409, stale.text


def test_unarchived_teaching_tasks_block_disband_until_archived(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, AaTeachingTaskBatch, AaTeachingTask
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    with get_sessionmaker()() as db:
        term = AaTerm(tenant_id=TID, year_code='2041-2042', term_no=1, status='DRAFT')
        db.add(term); db.flush()
        batch = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name='未完成学期', status='DRAFT')
        db.add(batch); db.flush()
        db.add(AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=9981, class_id=ids['cEmpty'], status='READY'))
        db.commit(); term_id = term.id
    row = _create(client, headers, [ids['cEmpty']])
    checked = _act(client, headers, row, 'precheck').json()['data']
    assert checked['checkResult']['blocked'] is True
    assert checked['checkResult']['refs'][0]['openTaskCount'] == 1
    with get_sessionmaker()() as db:
        db.get(AaTerm, term_id).status = 'ARCHIVED'
        db.commit()
    checked = _act(client, headers, row, 'precheck').json()['data']
    assert checked['checkResult']['blocked'] is False
    assert _act(client, headers, row, 'execute').status_code == 200


def test_deleted_or_disabled_class_is_not_treated_as_an_empty_valid_class(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    row = _create(client, headers, [ids['cEmpty']])
    with get_sessionmaker()() as db:
        db.get(SchoolClass, ids['cEmpty']).is_deleted = True
        db.commit()
    checked = _act(client, headers, row, 'precheck').json()['data']
    assert checked['checkResult']['blocked'] is True
    assert checked['checkResult']['refs'][0]['blockers']
    assert _act(client, headers, row, 'execute').status_code == 400


def test_duplicate_execution_has_one_receipt_and_one_audit(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail, SchoolClass
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    row = _create(client, headers, [ids['cEmpty']])
    _act(client, headers, row, 'precheck')
    barrier = Barrier(2)
    def execute():
        barrier.wait(timeout=10)
        return _act(client, headers, row, 'execute')
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(execute) for _ in range(2)]
        responses = [future.result(timeout=30) for future in futures]
    assert all(response.status_code == 200 for response in responses), [response.text for response in responses]
    assert responses[0].json()['data']['checkResult']['execution'] == responses[1].json()['data']['checkResult']['execution']
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == TID, AffairsAuditTrail.biz_type == 'AA_ORG_CLASS_ADJUST_REQUEST',
            AffairsAuditTrail.biz_id == int(row['id']), AffairsAuditTrail.action == 'ADJUST_EXECUTE')) == 1
        assert db.get(SchoolClass, ids['cEmpty']).version == 1


def test_batch_snapshot_preserves_more_than_old_varchar_limits(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    sources = [900000000000001000 + index for index in range(30)]
    with get_sessionmaker()() as db:
        db.add_all([SchoolClass(id=cid, tenant_id=TID, major_id=ids['majSw'], class_name=f'组织调整批量验收行政班{index:02}',
            class_status='NORMAL', status='ACTIVE') for index, cid in enumerate(sources)])
        db.commit()
    row = _create(client, headers, sources)
    checked = _act(client, headers, row, 'precheck')
    assert checked.status_code == 200, checked.text
    assert len(checked.json()['data']['checkResult']['refs']) == 30
    assert _act(client, headers, row, 'execute').status_code == 200


def test_stale_client_check_version_is_rejected_and_split_remains_record_only(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    row = _create(client, headers, [ids['c1']], 'SPLIT')
    first = _act(client, headers, row, 'precheck').json()['data']
    second = _act(client, headers, row, 'precheck').json()['data']
    assert 'version' in first and second['version'] > first['version']
    assert _act(client, headers, row, 'execute', expectedVersion=first['version']).status_code == 409
    result = _act(client, headers, row, 'execute', expectedVersion=second['version'])
    assert result.status_code == 200, result.text
    assert result.json()['data']['checkResult']['execution']['studentMoveCount'] == 0
    with get_sessionmaker()() as db:
        assert db.get(SchoolClass, ids['c1']).class_status == 'NORMAL'
        assert db.get(StudentProfile, ids['s1']).class_id == ids['c1']
