"""正式教学任务承接入口：真实 MySQL、正常权限链和写后回读。"""
import pytest

from tests.test_aa_schedule import BASE, TID
from tests.test_aa_task_source_handoff import _setup, _body, _task_snapshot
from tests.test_aa_task_source_review import _review


def _url(facts):
    return f"{BASE}/teaching-tasks/{facts['oldId']}/source-handoff"


def test_formal_api_confirms_then_replays_and_reads_same_receipt(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTaskSourceHandoff, AffairsAuditTrail, AaScheduleBatch, AaScheduleItem
    facts = _setup(client)
    with get_sessionmaker()() as db:
        published = AaScheduleBatch(tenant_id=TID, term_id=int(facts['termId']),
            batch_name='原任务既有发布历史', status='PUBLISHED')
        db.add(published); db.flush()
        history = AaScheduleItem(tenant_id=TID, batch_id=published.id, task_id=int(facts['oldId']),
            weekday=2, slot_no=1, start_week=1, end_week=18, week_parity='ALL', status='EFFECTIVE')
        db.add(history); db.commit()
        history_id, original_batch_id = history.id, published.id
        before = _task_snapshot(db, facts)
    body = vars(_body(client, facts))
    first = client.post(_url(facts), headers=facts['school'], json=body)
    assert first.status_code == 200, first.text
    receipt = first.json()['data']
    again = client.post(_url(facts), headers=facts['school'], json=body)
    assert again.status_code == 200, again.text
    assert again.json()['data'] == receipt
    readback = _review(client, facts)
    assert readback.status_code == 200, readback.text
    assert readback.json()['data']['confirmedHandoff'] == receipt
    with get_sessionmaker()() as db:
        assert _task_snapshot(db, facts) == before
        history = db.get(AaScheduleItem, history_id)
        assert (history.batch_id, history.task_id, history.status) == (original_batch_id, int(facts['oldId']), 'EFFECTIVE')
        assert db.get(AaScheduleBatch, original_batch_id).status == 'PUBLISHED'
        assert db.query(AaTeachingTaskSourceHandoff).filter_by(tenant_id=TID).count() == 1
        assert db.query(AffairsAuditTrail).filter_by(tenant_id=TID, biz_type='AA_TASK_SOURCE_HANDOFF').count() == 1


@pytest.mark.parametrize('invalid', ['college', 'stale', 'extra_field', 'missing_fingerprint'])
def test_formal_api_rejects_invalid_confirmation_without_writes(client, db_mode, invalid):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTaskSourceHandoff, AffairsAuditTrail
    facts = _setup(client)
    body = vars(_body(client, facts))
    headers, expected = facts['school'], 400
    if invalid == 'college':
        headers, expected = facts['college'], 403
    elif invalid == 'stale':
        body['expectedSourceFingerprint'], expected = '0' * 64, 409
    elif invalid == 'extra_field':
        body['tenantId'] = str(TID)
    else:
        body.pop('expectedSourceFingerprint')
    response = client.post(_url(facts), headers=headers, json=body)
    assert response.status_code == expected, response.text
    if invalid in {'extra_field', 'missing_fingerprint'}:
        assert response.json()['bizCode'] == 'VALIDATION_ERROR'
        field = 'tenantId' if invalid == 'extra_field' else 'expectedSourceFingerprint'
        assert any(item['field'] == field for item in response.json()['details'])
    with get_sessionmaker()() as db:
        assert db.query(AaTeachingTaskSourceHandoff).filter_by(tenant_id=TID).count() == 0
        assert db.query(AffairsAuditTrail).filter_by(tenant_id=TID, biz_type='AA_TASK_SOURCE_HANDOFF').count() == 0
