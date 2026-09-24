"""Batch constraints must narrow each workbench queue before pagination."""
from test_orientation_o3_self_service import _seed_o3, TID

def test_workbench_queues_keep_batch_context(client, db_mode, auth_headers):
    from app.db.session import get_sessionmaker
    from app.models import OrientationBatch, OrientationStudent, OrientationMaterial, GreenChannelApplication, OrientationException, OrientationPaymentAccount
    from app.services.orientation_flow_service import ensure_student_steps
    ids = _seed_o3(db_mode)
    expected = {}
    with get_sessionmaker()() as db:
        first = db.get(OrientationStudent, ids['orientationId'])
        original = db.get(OrientationBatch, first.batch_id)
        batch = OrientationBatch(tenant_id=TID, batch_no='QUEUE-OTHER', batch_name='另一批次', year='2026', status='ACTIVE', flow_version_id=original.flow_version_id)
        db.add(batch); db.flush()
        other = OrientationStudent(tenant_id=TID, batch_id=batch.id, student_id=ids['otherProfileId'], name='其他批次新生', admission_no='QUEUE-OTHER-STUDENT', source_type='MANUAL', source_record_id='QUEUE-OTHER-STUDENT', identity_status='LINKED', record_status='ACTIVE')
        db.add(other); db.flush(); ensure_student_steps(db, other, status_source='PROCESS_FACT')
        target_batch = first.batch_id
        for student in [first, other]:
            db.add(OrientationPaymentAccount(tenant_id=TID, orientation_student_id=student.id, student_id=student.student_id, status='UNPAID', source_type='LEGACY_BACKFILL', source_biz_id=f'queue:{student.id}'))
            rows = {
                'materials': OrientationMaterial(tenant_id=TID, ori_student_id=student.id, material_type='PHOTO', file_name='queue-only.png', is_current=True),
                'green-channels': GreenChannelApplication(tenant_id=TID, ori_student_id=student.id, student_id=student.student_id, apply_type='DEFERRED'),
                'exceptions': OrientationException(tenant_id=TID, ori_student_id=student.id, exception_type='MATERIAL'),
            }
            db.add_all(rows.values()); db.flush()
            if student.id == first.id: expected = {key:str(row.id) for key,row in rows.items()}
        db.commit()
    for path, wanted in expected.items():
        result = client.get('/api/v1/orientation/'+path, headers=auth_headers, params={'batchId':target_batch,'pageSize':1})
        assert result.status_code == 200, result.text
        data = result.json()['data']
        assert data['total'] == 1 and data['items'][0]['id'] == wanted
        empty = client.get('/api/v1/orientation/'+path, headers=auth_headers, params={'batchId':99999999}).json()['data']
        assert empty['total'] == 0
    for path in ['payments', 'qualifications', 'dorms']:
        for params in [{'batchId': target_batch}, {'orientationStudentId': ids['orientationId']}]:
            data = client.get('/api/v1/orientation/'+path, headers=auth_headers, params={**params, 'pageSize': 1}).json()['data']
            assert data['total'] == 1 and data['items'][0]['id'] == str(ids['orientationId'])
        data = client.get('/api/v1/orientation/'+path, headers=auth_headers, params={'batchId': target_batch, 'orientationStudentId': str(other.id)}).json()['data']
        assert data['total'] == 0
    data = client.get('/api/v1/orientation/green-channels', headers=auth_headers, params={'orientationStudentId': ids['orientationId']}).json()['data']
    assert data['total'] == 1 and data['items'][0]['studentId'] == str(ids['orientationId'])


def test_mobile_green_queue_filters_pending_and_batch_before_paging(client, db_mode, auth_headers):
    from app.db.session import get_sessionmaker
    from app.models import OrientationBatch, OrientationStudent, GreenChannelApplication
    from test_orientation_o3_self_service import _token

    ids = _seed_o3(db_mode)
    with get_sessionmaker()() as db:
        first = db.get(OrientationStudent, ids['orientationId'])
        target_batch = first.batch_id
        pending = [GreenChannelApplication(
            tenant_id=TID, ori_student_id=first.id, student_id=first.student_id,
            apply_type='TUITION_DEFERMENT', status=status,
        ) for status in ('SUBMITTED', 'REVIEWING')]
        db.add_all(pending); db.flush()
        expected_ids = {str(row.id) for row in pending}
        db.add_all([GreenChannelApplication(
            tenant_id=TID, ori_student_id=first.id, student_id=first.student_id,
            apply_type='TUITION_DEFERMENT', status='APPROVED',
        ) for _ in range(55)])
        original_batch = db.get(OrientationBatch, target_batch)
        other_batch = OrientationBatch(tenant_id=TID, batch_no='MOBILE-GREEN-OTHER', batch_name='其他迎新批次', year='2026', status='ACTIVE', flow_version_id=original_batch.flow_version_id)
        db.add(other_batch); db.flush()
        other = OrientationStudent(tenant_id=TID, batch_id=other_batch.id, student_id=ids['otherProfileId'], name='其他批次同学', admission_no='MOBILE-GREEN-OTHER', source_type='MANUAL', source_record_id='MOBILE-GREEN-OTHER', identity_status='LINKED', record_status='ACTIVE')
        db.add(other); db.flush()
        db.add(GreenChannelApplication(tenant_id=TID, ori_student_id=other.id, student_id=other.student_id, apply_type='TUITION_DEFERMENT', status='SUBMITTED'))
        db.commit()

    endpoint = '/api/v1/mobile/teacher/orientation/green-channels'
    def get(**params):
        result = client.get(endpoint, headers=auth_headers, params={'batchId': target_batch, **params})
        assert result.status_code == 200, result.text
        return result.json()['data']

    first_page = get(page=1, pageSize=1)
    second_page = get(page=2, pageSize=1)
    assert first_page['total'] == second_page['total'] == 2
    assert {first_page['list'][0]['id'], second_page['list'][0]['id']} == expected_ids
    assert get()['total'] == 2
    assert get(queue='all', pageSize=100)['total'] == 57
    assert get(status='APPROVED')['total'] == 55, 'Explicit status remains compatible with the existing endpoint'
    assert get(batchId=99999999)['total'] == 0
    assert get(batchId=other_batch.id)['total'] == 1
    assert client.get(endpoint, headers=auth_headers, params={'pageSize': 101}).status_code >= 400
    assert client.get(endpoint, headers=auth_headers, params={'queue': 'unknown'}).status_code >= 400
    student = _token(user_id=ids['userId'], student_id=ids['profileId'], student_no=ids['studentNo'], name=ids['name'])
    denied = client.get(endpoint, headers=student, params={'batchId': target_batch})
    assert denied.status_code == 403, denied.text

