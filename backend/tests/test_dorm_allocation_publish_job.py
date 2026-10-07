from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import func, select

from tests.test_dorm_d3_allocation import BASE, TID, _admin, _create, _seed_authorities


def prepare(client, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import User
    from app.services import dorm_allocation_publish_job as jobs
    seeded = _seed_authorities(students=3, beds=3)
    with get_sessionmaker()() as db:
        actor = User(tenant_id=TID, login_name='school_admin01', real_name='发布测试人员',
                     user_type='ADMIN', status='ACTIVE', password_hash='not-for-login')
        db.add(actor); db.commit(); actor_id = actor.id
    headers = _admin(client)
    batch = _create(client, headers, seeded, 'ADMIN_AUTO', 'ASYNC')
    assert client.post(f'{BASE}/{batch}/dry-run', headers=headers).status_code == 200
    version = client.get(f'{BASE}/{batch}', headers=headers).json()['data']['batch']['version']
    # Isolate job/transaction tests from login policy; revocation uses real account resolution below.
    monkeypatch.setattr(jobs, '_live_actor', lambda db, snapshot: {
        **snapshot, 'currentRoleCode': 'SCHOOL_ADMIN', 'realName': '发布测试人员',
    })
    return seeded, headers, batch, version, actor_id


def test_publish_queue_is_read_only_idempotent_and_worker_commits_receipt(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import DormStay, DormAllocationBatch
    from app.models.affairs_operations import AffairsBatchJob
    from app.services import dorm_allocation_publish_job as jobs
    seeded, headers, batch, version, _ = prepare(client, monkeypatch)
    path = f'{BASE}/{batch}/publish-jobs'
    result = client.post(path, headers=headers, json={'version': version})
    assert result.status_code == 200, result.text
    job_id = result.json()['data']['jobId']
    assert result.json()['data']['status'] == 'PENDING'
    assert client.post(path, headers=headers, json={'version': version}).json()['data']['jobId'] == job_id
    for _ in range(2):
        assert client.get(path+'/latest', headers=headers).json()['data']['status'] == 'PENDING'
    # The legacy material-reminder API cannot expose housing job details/actors.
    legacy = client.get('/api/v1/student-affairs/batch-jobs', headers=headers)
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()['data']['total'] == 0
    assert client.get(f'/api/v1/student-affairs/batch-jobs/{job_id}', headers=headers).status_code == 404
    with get_sessionmaker()() as db:
        reminder = AffairsBatchJob(tenant_id=TID, batch_no='REMIND-SCOPE', job_type='MATERIAL_REMIND',
                                  idempotency_key='remind-scope-test', requested_by='test',
                                  status='SUCCESS', total_count=0, success_count=0, failure_count=0,
                                  pending_count=0, request_json={})
        db.add(reminder); db.commit(); reminder_id = reminder.id
    assert client.get('/api/v1/student-affairs/batch-jobs', headers=headers).json()['data']['total'] == 1
    assert client.get(f'/api/v1/student-affairs/batch-jobs/{reminder_id}', headers=headers).status_code == 200
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(DormStay)) == 0
        # A previous worker exited after claiming. The next worker must resume.
        db.get(AffairsBatchJob, int(job_id)).status = 'RUNNING'; db.commit()
    result = jobs.run_one()
    assert result['status'] == 'SUCCESS' and result['success'] == 3
    assert jobs.run_one()['processed'] is False
    with get_sessionmaker()() as db:
        assert db.get(DormAllocationBatch, int(batch)).status == 'PUBLISHED'
        assert db.scalar(select(func.count()).select_from(DormStay)) == 3
        assert all(s.status == 'RESERVED' and s.checkin_at is None for s in db.scalars(select(DormStay)))
    assert client.get(path+'/latest', headers=headers).json()['data']['status'] == 'SUCCESS'


def test_worker_crash_rolls_back_and_concurrent_worker_does_not_repeat(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import DormStay, DormAllocationBatch
    from app.services import dorm_allocation_publish_job as jobs
    _, headers, batch, version, _ = prepare(client, monkeypatch)
    path = f'{BASE}/{batch}/publish-jobs'
    assert client.post(path, headers=headers, json={'version': version}).status_code == 200
    original = jobs.allocation.publish_in_transaction
    def crash(db, *args, **kwargs):
        original(db, *args, **kwargs)
        raise RuntimeError('interrupted before publication receipt commit')
    monkeypatch.setattr(jobs.allocation, 'publish_in_transaction', crash)
    with pytest.raises(RuntimeError):
        jobs.run_one()
    with get_sessionmaker()() as db:
        assert db.get(DormAllocationBatch, int(batch)).status == 'DRAFT'
        assert db.scalar(select(func.count()).select_from(DormStay)) == 0
    entered, release = Event(), Event()
    def held(db, *args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(db, *args, **kwargs)
    monkeypatch.setattr(jobs.allocation, 'publish_in_transaction', held)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(jobs.run_one)
        try:
            assert entered.wait(10)
            assert executor.submit(jobs.run_one).result(timeout=5)['processed'] is False
        finally:
            release.set()
        assert first.result(timeout=30)['status'] == 'SUCCESS'
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(DormStay)) == 3


def test_queued_publish_rejects_new_plan_version_and_disabled_actor(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import DormStay, DormAllocationBatch, User
    from app.services import dorm_allocation_publish_job as jobs
    original_actor = jobs._live_actor
    _, headers, batch, version, actor_id = prepare(client, monkeypatch)
    path = f'{BASE}/{batch}/publish-jobs'
    assert client.post(path, headers=headers, json={'version': version}).status_code == 200
    with get_sessionmaker()() as db:
        db.get(DormAllocationBatch, int(batch)).version += 1; db.commit()
    result = jobs.run_one()
    assert result['status'] == 'FAILED' and '变化' in result['error']
    assert client.post(path, headers=headers, json={'version': version+1}).status_code == 200
    with get_sessionmaker()() as db:
        db.get(User, actor_id).status = 'DISABLED'; db.commit()
    monkeypatch.setattr(jobs, '_live_actor', original_actor)
    result = jobs.run_one()
    assert result['status'] == 'FAILED' and '停用' in result['error']
    with get_sessionmaker()() as db:
        assert db.get(DormAllocationBatch, int(batch)).status == 'DRAFT'
        assert db.scalar(select(func.count()).select_from(DormStay)) == 0
