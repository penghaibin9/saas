"""Registration archive fences through real HTTP and isolated MySQL transactions."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from app.db.session import get_sessionmaker
from test_aa_registration_batch_rowlock import (
    BASE, TID, _headers, _post, _pause_first_batch_select,
    _await_wait_or_completion, _assert_real_wait,
)


def _initial_records(client, db_mode):
    from app.models import SchoolClass, StudentProfile
    with get_sessionmaker()() as db:
        school_class = SchoolClass(tenant_id=TID, major_id=1, class_name='Archive fence',
                                   grade='2026', status='ACTIVE')
        db.add(school_class)
        db.flush()
        students = [StudentProfile(tenant_id=TID, student_no='AF-' + uuid4().hex[:12],
                    real_name='Archive fixture', class_id=school_class.id,
                    current_stage='ORIENTATION', student_status='PENDING_REGISTER', status='ACTIVE')
                    for _ in range(2)]
        db.add_all(students)
        db.flush()
        ids = [str(row.id) for row in students]
        db.commit()
    headers = _headers(client)
    batch = client.post(BASE + '/registration-batches', headers=headers,
                        json={'batchName': 'Archive fence', 'registerType': 'ENROLL', 'open': True})
    assert batch.status_code == 200, batch.text
    batch_id = batch.json()['data']['batchId']
    deferred = client.post(f'{BASE}/registration-batches/{batch_id}/deferrals', headers=headers,
                           json={'studentId': ids[0], 'reason': '正式测试暂缓'})
    exception = client.post(f'{BASE}/registration-batches/{batch_id}/exceptions', headers=headers,
                            json={'studentId': ids[0], 'exceptionType': 'OTHER', 'description': '正式测试异常'})
    assert deferred.status_code == exception.status_code == 200, (deferred.text, exception.text)
    return headers, batch_id, ids, deferred.json()['data']['deferralId'], exception.json()['data']['exceptionId']


def _snapshot(batch_id):
    from app.models import AaRegistrationDeferral, AaRegistrationException, AffairsAuditTrail
    with get_sessionmaker()() as db:
        deferrals = [(str(row.id), row.status, row.review_note) for row in
                     db.query(AaRegistrationDeferral).filter_by(batch_id=int(batch_id)).order_by(AaRegistrationDeferral.id)]
        exceptions = [(str(row.id), row.status, row.resolution_note) for row in
                      db.query(AaRegistrationException).filter_by(batch_id=int(batch_id)).order_by(AaRegistrationException.id)]
        return deferrals, exceptions, db.query(AffairsAuditTrail).filter_by(tenant_id=TID).count()


def test_archived_batch_rejects_all_four_related_writes_without_audit_or_state_changes(client, db_mode):
    headers, bid, students, did, eid = _initial_records(client, db_mode)
    assert _post(client, headers, bid, 'close').status_code == 200
    # Closing does not invent a new prohibition on existing exception handling.
    closed_exception = client.post(f'{BASE}/registration-batches/{bid}/exceptions', headers=headers,
        json={'studentId': students[1], 'exceptionType': 'OTHER', 'description': '关闭后处理历史异常'})
    assert closed_exception.status_code == 200, closed_exception.text
    assert _post(client, headers, bid, 'archive').status_code == 200
    before = _snapshot(bid)
    requests = [
        (f'/registration-batches/{bid}/deferrals', {'studentId': students[1], 'reason': '不能追加暂缓'}),
        (f'/registration-batches/{bid}/exceptions', {'studentId': students[1], 'exceptionType': 'OTHER', 'description': '不能追加异常'}),
        (f'/registration/deferrals/{did}/review', {'action': 'APPROVE', 'note': '不能归档后审批'}),
        (f'/registration/exceptions/{eid}/resolve', {'note': '不能归档后处理'}),
    ]
    responses = [client.post(BASE + path, headers=headers, json=body) for path, body in requests]
    assert [r.status_code for r in responses] == [409] * 4, [r.text for r in responses]
    assert all('归档' in r.text for r in responses)
    assert _snapshot(bid) == before


def test_deferral_review_waits_for_archive_then_rechecks_current_batch(client, db_mode, monkeypatch):
    headers, bid, _students, did, _eid = _initial_records(client, db_mode)
    assert _post(client, headers, bid, 'close').status_code == 200
    before = _snapshot(bid)
    reached, release, evidence = _pause_first_batch_select(monkeypatch, bid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        archived = pool.submit(_post, client, headers, bid, 'archive')
        try:
            assert reached.wait(5)
            review = pool.submit(client.post, f'{BASE}/registration/deferrals/{did}/review',
                                 headers=headers, json={'action': 'APPROVE', 'note': '并发审批'})
            waits = _await_wait_or_completion(review, bid)
            _assert_real_wait(waits, evidence, bid)
            release.set()
            assert archived.result(timeout=5).status_code == 200
            response = review.result(timeout=5)
            assert response.status_code == 409 and '归档' in response.text, response.text
        finally:
            release.set()
    after = _snapshot(bid)
    assert after[:2] == before[:2]
    assert after[2] == before[2] + 1  # Only the formal ARCHIVE audit was committed.
