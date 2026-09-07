"""Batch constraints must narrow each workbench queue before pagination."""
from test_orientation_o3_self_service import _seed_o3, TID

def test_workbench_queues_keep_batch_context(client, db_mode, auth_headers):
    from app.db.session import get_sessionmaker
    from app.models import OrientationBatch, OrientationStudent, OrientationMaterial, GreenChannelApplication, OrientationException
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

