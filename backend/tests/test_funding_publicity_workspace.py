"""Funding publicity: real HTTP scan, complete pagination and scoped candidates."""
from datetime import datetime, timedelta
from test_funding_application_workspace import _accounts, _project_batch, _login, _data, BASE, TID


def test_publicity_complete_window_batch_scope_and_appeals(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, FundingBatch, FundingAppeal, StudentProfile
    from app.services import affairs_dashboard_service as dashboard
    ids = _accounts(db_mode)
    admin = _login(client, 'school_admin01', 'PC')
    student = _login(client, 'fund_student', 'PC')
    project, batch = _project_batch(client, admin)
    other_batch = _data(client.post(BASE+'/funding/batches', headers=admin, json={
        'projectId':project['projectId'], 'schoolYear':'2027-2028', 'publicityDays':1, 'quota':10, 'publish':True}))
    now = datetime.utcnow()
    with get_sessionmaker()() as db:
        college = db.get(StudentProfile, ids['sa']).college_id
        waiting = []
        for i in range(202):
            s = StudentProfile(tenant_id=TID, student_no=f'PUB{i:03}', real_name=f'公示验收{i}',
                class_id=ids['A'], college_id=college, current_stage='ORIENTATION', student_status='NORMAL', status='ACTIVE')
            db.add(s); db.flush()
            row = FundingApplication(tenant_id=TID, batch_id=int(batch['batchId']), student_id=s.id,
                project_type='SCHOLARSHIP', apply_source='SELF', status='PUBLICITY',
                publicity_at=now if i < 201 else now-timedelta(days=2), amount=3000, requested_amount=3000)
            db.add(row); db.flush(); waiting.append(row.id)
        pending_id = waiting[-1]
        db.add(FundingAppeal(tenant_id=TID, application_id=pending_id, student_id=s.id,
            status='SUBMITTED', reason='公示信息需要复核', open_key=pending_id))
        due = FundingApplication(tenant_id=TID, batch_id=int(batch['batchId']), student_id=ids['sa'],
            project_type='SCHOLARSHIP', apply_source='SELF', status='PUBLICITY',
            publicity_at=now-timedelta(days=2), amount=3000, requested_amount=3000)
        outside = FundingApplication(tenant_id=TID, batch_id=int(batch['batchId']), student_id=ids['sb'],
            project_type='SCHOLARSHIP', apply_source='SELF', status='PUBLICITY',
            publicity_at=now-timedelta(days=2), amount=3000, requested_amount=3000)
        other = FundingApplication(tenant_id=TID, batch_id=int(other_batch['batchId']), student_id=ids['sa'],
            project_type='SCHOLARSHIP', apply_source='SELF', status='PUBLICITY',
            publicity_at=now-timedelta(days=2), amount=3000, requested_amount=3000)
        db.add_all([due, outside, other]); db.commit()
        due_id, outside_id, other_id = due.id, outside.id, other.id
    seen = []
    for page in range(1,12):
        data = _data(client.get(BASE+'/funding/applications', headers=admin,
            params={'batchId':batch['batchId'],'status':'PUBLICITY','page':page,'pageSize':20}))
        assert data['total'] == 204
        seen.extend(x['applicationId'] for x in data['items'])
        for row in data['items']:
            if row['applicationId'] in [str(due_id),str(outside_id)]:
                assert row['allowedActions'] == ['PUBLICITY_CONFIRM'] and row['publicityReady']
            else:
                assert row['allowedActions'] == [] and not row['publicityReady']
    assert len(seen) == len(set(seen)) == 204
    assert client.post(BASE+'/funding/scan-publicity', headers=student, json={}).status_code == 403
    assert client.post(BASE+'/funding/scan-publicity', headers=admin, json={'batchId':-1}).status_code == 400
    # Exercise the same scope resolver used by list and write; the HTTP permission remains real.
    monkeypatch.setattr(dashboard, '_allowed_class_ids', lambda db, user: ({ids['A']}, None))
    result = _data(client.post(BASE+'/funding/scan-publicity', headers=admin, json={'batchId':batch['batchId']}))
    assert result['count'] == 1 and result['skippedAppeal'] == 1 and result['notDue'] == 201
    with get_sessionmaker()() as db:
        assert db.get(FundingApplication,due_id).status == 'GRANTED'
        assert db.get(FundingApplication,outside_id).status == 'PUBLICITY'
        assert db.get(FundingApplication,other_id).status == 'PUBLICITY'
        assert db.get(FundingApplication,pending_id).status == 'PUBLICITY'
        assert db.get(FundingApplication,waiting[0]).status == 'PUBLICITY'
    assert _data(client.post(BASE+'/funding/scan-publicity', headers=admin, json={'batchId':batch['batchId']}))['count'] == 0
    # Bodyless legacy manual caller retains compatibility and still respects the caller's range.
    assert _data(client.post(BASE+'/funding/scan-publicity', headers=admin))['count'] == 1
    monkeypatch.undo()
    assert _data(client.post(BASE+'/funding/scan-publicity', headers=admin, json={'batchId':batch['batchId']}))['count'] == 1
    # A deleted batch cannot be manually confirmed through the former five-day fallback.
    with get_sessionmaker()() as db:
        row = db.get(FundingApplication,waiting[0]); row.publicity_at = now-timedelta(days=10)
        version = row.version; db.get(FundingBatch,int(batch['batchId'])).is_deleted=True; db.commit()
    rejected = client.post(BASE+f'/funding/applications/{waiting[0]}/publicity-confirm',headers=admin,json={'version':version})
    assert rejected.status_code == 409
