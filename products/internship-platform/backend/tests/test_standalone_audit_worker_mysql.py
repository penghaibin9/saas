"""Real MySQL queue delivery; each case owns an isolated synthetic tenant."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from app.config import settings
from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.audit import SecurityAuditLog
from app.models.audit_outbox import AuditOutbox
from app.modules.internship.services import internship_audit_service as service


@pytest.fixture
def tenant():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL acceptance required')
    url = make_url(settings.DATABASE_URL)
    assert settings.APP_ENV == 'test' and url.get_backend_name() == 'mysql'
    assert any(x in (url.database or '').lower() for x in ('_test', '_ci', 'gap09'))
    tid = 910000000000 + int(uuid.uuid4().hex[:9], 16)
    set_tenant(tid)
    try:
        yield tid
    finally:
        set_current_user(None)
        set_tenant(None)
        with get_sessionmaker()() as db:
            db.execute(delete(SecurityAuditLog).where(SecurityAuditLog.tenant_id == tid))
            db.execute(delete(AuditOutbox).where(AuditOutbox.tenant_id == tid))
            db.commit()


def enqueue(tenant, **kwargs):
    payload = kwargs.pop('payload', {'tenantId': str(tenant), 'targetType': 'TEST', 'targetId': '77'})
    with get_sessionmaker()() as db:
        row = AuditOutbox(tenant_id=tenant, event_id=uuid.uuid4().hex,
                          event_type='IX_DELIVERY_TEST', payload_json=payload, status='PENDING')
        for key, value in kwargs.items():
            setattr(row, key, value)
        db.add(row)
        db.commit()
        return row.id


def rows(tenant):
    with get_sessionmaker()() as db:
        return db.scalars(select(SecurityAuditLog).where(SecurityAuditLog.tenant_id == tenant)).all()


def state(row_id):
    with get_sessionmaker()() as db:
        return db.get(AuditOutbox, row_id)


def test_original_actor_not_worker_context_and_payload_is_redacted(tenant):
    set_current_user({'userId': 'db-999', 'realName': 'Wrong worker identity', 'currentRoleCode': 'SYSTEM'})
    rid = enqueue(tenant, payload={'tenantId': str(tenant), 'targetType': 'REPORT', 'targetId': '77',
        'actorUserId': 'db-88011', 'actorName': '原审核教师', 'actorRole': 'INTERN_MENTOR',
        'internshipId': '123456', 'detailJson': {'password': 'never-store-this', 'phone': '13800000000'}})
    service.process_pending(limit=1000)
    log, = rows(tenant)
    assert (log.operator_id, log.operator_name, log.current_role) == (88011, '原审核教师', 'INTERN_MENTOR')
    assert log.tenant_id == tenant and log.resource_id == '77'
    assert log.detail_json['internshipId'] == '123456'
    assert 'never-store-this' not in str(log.detail_json) and '13800000000' not in str(log.detail_json)
    assert log.source_event_id == state(rid).event_id


def test_bad_database_row_does_not_poison_good_row_and_error_has_no_payload(tenant):
    bad = enqueue(tenant, payload={'tenantId': str(tenant), 'targetId': 'sensitive-' + 'x' * 150})
    good = enqueue(tenant)
    service.process_pending(limit=1000)
    assert state(bad).status == 'RETRY_WAIT'
    assert state(bad).retry_count == 1 and state(bad).next_retry_at > datetime.utcnow()
    assert 'sensitive-' not in state(bad).last_error
    assert 'INSERT INTO' not in state(bad).last_error
    assert state(good).status == 'PROCESSED'
    assert len(rows(tenant)) == 1


def test_future_retry_not_consumed_due_retry_cleared_and_terminal_failure_preserved(tenant):
    future = enqueue(tenant, status='RETRY_WAIT', next_retry_at=datetime.utcnow() + timedelta(hours=2))
    due = enqueue(tenant, status='RETRY_WAIT', retry_count=2, next_retry_at=datetime.utcnow() - timedelta(seconds=1), last_error='prior error')
    dead = enqueue(tenant, retry_count=9, payload={'tenantId': str(tenant), 'targetId': 'x' * 200})
    service.process_pending(limit=1000)
    assert state(future).status == 'RETRY_WAIT'
    assert state(due).status == 'PROCESSED' and state(due).next_retry_at is None
    assert state(due).last_error is None
    assert state(dead).status == 'DEAD' and state(dead).retry_count == 10
    assert state(dead).payload_json['targetId'] == 'x' * 200


def test_replayed_outbox_event_is_not_persisted_twice(tenant):
    rid = enqueue(tenant)
    service.process_pending(limit=1000)
    with get_sessionmaker()() as db:
        row = db.get(AuditOutbox, rid)
        row.status = 'PENDING'
        db.commit()
    service.process_pending(limit=1000)
    assert state(rid).status == 'PROCESSED'
    assert len(rows(tenant)) == 1


def test_concurrent_workers_deliver_each_event_once(tenant):
    ids = [enqueue(tenant) for _ in range(24)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: service.process_pending(limit=1000, worker_id=f'test-{i}'), range(4)))
    assert len(rows(tenant)) == 24
    assert all(state(i).status == 'PROCESSED' for i in ids)
    assert len({r.source_event_id for r in rows(tenant)}) == 24


def test_transaction_failure_preserves_pending_for_next_run(tenant, monkeypatch):
    import app.db.session as session_module
    rid = enqueue(tenant)
    factory = get_sessionmaker()
    broken = factory()
    def fail_commit():
        raise RuntimeError('simulated connection failure before commit')
    monkeypatch.setattr(broken, 'commit', fail_commit)
    with monkeypatch.context() as patch:
        patch.setattr(session_module, 'get_sessionmaker', lambda: lambda: broken)
        with pytest.raises(RuntimeError):
            service.process_pending(limit=1000)
    assert state(rid).status == 'PENDING' and rows(tenant) == []
    service.process_pending(limit=1000)
    assert state(rid).status == 'PROCESSED' and len(rows(tenant)) == 1


def test_cross_tenant_payload_is_not_misattributed(tenant):
    rid = enqueue(tenant, payload={'tenantId': str(tenant + 1), 'targetId': '77'})
    service.process_pending(limit=1000)
    assert state(rid).status == 'RETRY_WAIT' and rows(tenant) == []


def test_stalled_gate_recovers_only_after_real_delivery_and_dead_stays_blocked(tenant):
    enqueue(tenant, created_at=datetime.utcnow() - timedelta(hours=2))
    with get_sessionmaker()() as db:
        with pytest.raises(AppException):
            service.assert_high_risk_write_available(db)
    service.process_pending(limit=1000)
    with get_sessionmaker()() as db:
        assert service.assert_high_risk_write_available(db)['healthy'] is True
    enqueue(tenant, status='DEAD')
    with get_sessionmaker()() as db:
        with pytest.raises(AppException):
            service.assert_high_risk_write_available(db)


@pytest.mark.parametrize('limit', [0, -1, 1001, True])
def test_invalid_batch_size_rejected_without_reading_database(limit):
    with pytest.raises(ValueError):
        service.process_pending(limit=limit)
