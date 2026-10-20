"""T06 MySQL registration batch transition concurrency regression.

Candidate for backend/tests. Reuses the existing isolated db_mode/role fixtures.
Business outcomes are created only through the formal HTTP commands.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from time import monotonic, sleep
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql import visitors

import pytest

from app.db.session import get_engine, get_sessionmaker

TID = 1000000000000000001
BASE = '/api/v1/academic-affairs'


def _headers(client, login_name='school_admin01'):
    response = client.post('/api/v1/auth/mock-login', json={'loginName': login_name, 'password': 'any'})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['data']['accessToken']}


def _create(client, headers, opened=True):
    response = client.post(BASE + '/registration-batches', headers=headers,
                           json={'batchName': 'T06-lock-' + uuid4().hex[:10], 'registerType': 'ANNUAL', 'open': opened})
    assert response.status_code == 200, response.text
    return response.json()['data']['batchId']


def _post(client, headers, batch_id, action):
    return client.post(f'{BASE}/registration-batches/{batch_id}/{action}', headers=headers)


def _status(batch_id):
    from app.models import AaRegistrationBatch
    with get_sessionmaker()() as db:
        return db.get(AaRegistrationBatch, int(batch_id)).status


def _selected_batch_id(statement, params):
    """Read the exact batch PK bind from the real ORM statement, including Session.get."""
    if not getattr(statement, 'is_select', False):
        return None
    if not any(getattr(table, 'name', '') == 't_aa_registration_batch'
               for table in statement.get_final_froms()):
        return None
    compiled = statement.compile()
    values = dict(compiled.params)
    values.update(params or {})
    for expression in visitors.iterate(statement.whereclause):
        left, right = getattr(expression, 'left', None), getattr(expression, 'right', None)
        if (getattr(left, 'name', '') == 'id'
                and getattr(getattr(left, 'table', None), 'name', '') == 't_aa_registration_batch'):
            key = compiled.bind_names.get(right)
            value = values.get(key, getattr(right, 'value', None))
            if value is not None:
                return str(value)
    return None


def _pause_first_batch_select(monkeypatch, batch_id, also_observe=()):
    """Pause after the real PK SELECT; both execute/get and scalars use this entry."""
    reached, release = Event(), Event()
    claimed = Lock()
    original = Session._execute_internal
    observed_ids = {str(batch_id), *(str(value) for value in also_observe)}
    state = {'first': True, 'selects': []}

    def execute(session, statement, params=None, *args, **kwargs):
        selected_id = _selected_batch_id(statement, params)
        pause = False
        if selected_id in observed_ids:
            with claimed:
                state['selects'].append({
                    'batchId': selected_id,
                    'connectionId': session.connection().connection.driver_connection.thread_id(),
                    'forUpdate': getattr(statement, '_for_update_arg', None) is not None,
                })
                if selected_id == str(batch_id) and state['first']:
                    state['first'] = False
                    pause = True
        result = original(session, statement, params, *args, **kwargs)
        if pause:
            reached.set()
            if not release.wait(12):
                raise AssertionError('Test barrier timed out; this is not a business receipt')
        return result

    monkeypatch.setattr(Session, '_execute_internal', execute)
    return reached, release, state


def _lock_wait_rows(batch_id):
    engine = get_engine()
    assert engine.dialect.name == 'mysql', 'This concurrency acceptance requires real MySQL'
    with engine.connect() as observer:
        return [dict(row) for row in observer.execute(text("""
            SELECT bt.PROCESSLIST_ID AS blocker, rt.PROCESSLIST_ID AS waiter,
                   b.LOCK_DATA AS batchId
            FROM performance_schema.data_lock_waits w
            JOIN performance_schema.data_locks b
              ON b.ENGINE_LOCK_ID = w.BLOCKING_ENGINE_LOCK_ID AND b.ENGINE = w.ENGINE
            JOIN performance_schema.threads bt ON bt.THREAD_ID = w.BLOCKING_THREAD_ID
            JOIN performance_schema.threads rt ON rt.THREAD_ID = w.REQUESTING_THREAD_ID
            WHERE b.OBJECT_SCHEMA = :schema AND b.OBJECT_NAME = 't_aa_registration_batch'
              AND b.INDEX_NAME = 'PRIMARY' AND b.LOCK_DATA = :batch_id
        """), {'schema': engine.url.database, 'batch_id': str(batch_id)}).mappings()]


def _await_wait_or_completion(future, batch_id):
    deadline = monotonic() + 5
    while monotonic() < deadline and not future.done():
        waits = _lock_wait_rows(batch_id)
        if waits:
            return waits
        sleep(0.02)
    return []


def _assert_real_wait(waits, evidence, batch_id):
    assert waits, 'No actual MySQL row-lock wait was observed; thread timing is not evidence'
    first, second = evidence['selects'][:2]
    assert first['batchId'] == second['batchId'] == str(batch_id)
    assert first['forUpdate'] and second['forUpdate']
    assert first['connectionId'] != second['connectionId']
    assert any(row['blocker'] == first['connectionId'] and row['waiter'] == second['connectionId']
               and row['batchId'] == str(batch_id) for row in waits), (waits, evidence)
    print({'batchRowLockEvidence': waits, 'selects': evidence['selects'][:2]})


def test_same_batch_close_cannot_overwrite_an_archived_state(client, db_mode, monkeypatch):
    del db_mode
    headers = _headers(client)
    batch_id = _create(client, headers)
    reached, release, evidence = _pause_first_batch_select(monkeypatch, batch_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_post, client, headers, batch_id, 'close')
        try:
            assert reached.wait(5), 'First close did not reach the actual batch SELECT'
            second = pool.submit(_post, client, headers, batch_id, 'close')
            waits = _await_wait_or_completion(second, batch_id)
            if second.done():
                # Baseline red path: the later request advances to ARCHIVED while A holds an old OPEN snapshot.
                assert second.result().status_code == 200, second.result().text
                archived = _post(client, headers, batch_id, 'archive')
                assert archived.status_code == 200, archived.text
                release.set()
                assert first.result(timeout=5).status_code == 200
                final = _status(batch_id)
                assert final == 'ARCHIVED', f'Late close overwrote ARCHIVED: final={final}, selects={evidence["selects"]}'
            else:
                _assert_real_wait(waits, evidence, batch_id)
                release.set()
                response_a, response_b = first.result(timeout=5), second.result(timeout=5)
                assert response_a.status_code == 200, response_a.text
                assert response_a.json()['data']['status'] == 'CLOSED'
                assert response_b.status_code == 409, response_b.text
                archived = _post(client, headers, batch_id, 'archive')
                assert archived.status_code == 200, archived.text
                assert _post(client, headers, batch_id, 'close').status_code == 409
                assert _status(batch_id) == 'ARCHIVED'
        finally:
            release.set()
    from app.models import AffairsAuditTrail
    with get_sessionmaker()() as db:
        for action in ['CLOSE', 'ARCHIVE']:
            assert db.query(AffairsAuditTrail).filter_by(tenant_id=TID, biz_type='AA_REG_BATCH', biz_id=int(batch_id), action=action).count() == 1


@pytest.mark.parametrize('following_action, expected_status', [('close', 409), ('archive', 200)])
def test_waiting_command_rereads_archived_after_real_row_lock(client, db_mode, monkeypatch,
                                                            following_action, expected_status):
    del db_mode
    headers = _headers(client)
    batch_id = _create(client, headers)
    assert _post(client, headers, batch_id, 'close').status_code == 200
    reached, release, evidence = _pause_first_batch_select(monkeypatch, batch_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_post, client, headers, batch_id, 'archive')
        try:
            assert reached.wait(5), 'Archive did not reach its exact batch PK SELECT'
            second = pool.submit(_post, client, headers, batch_id, following_action)
            waits = _await_wait_or_completion(second, batch_id)
            _assert_real_wait(waits, evidence, batch_id)
            release.set()
            archived, following = first.result(timeout=5), second.result(timeout=5)
            assert archived.status_code == 200, archived.text
            assert archived.json()['data']['batchId'] == batch_id
            assert archived.json()['data']['status'] == 'ARCHIVED'
            assert following.status_code == expected_status, following.text
            if following_action == 'close':
                assert 'ARCHIVED' in following.text, following.text
            else:
                assert following.json()['data']['batchId'] == batch_id
                assert following.json()['data']['status'] == 'ARCHIVED'
            assert _status(batch_id) == 'ARCHIVED'
        finally:
            release.set()
    from app.models import AffairsAuditTrail
    with get_sessionmaker()() as db:
        assert db.query(AffairsAuditTrail).filter_by(tenant_id=TID, biz_type='AA_REG_BATCH',
            biz_id=int(batch_id), action='ARCHIVE').count() == 1


def test_holding_one_batch_does_not_block_another_batch_close(client, db_mode, monkeypatch):
    del db_mode
    headers = _headers(client)
    batch_a, batch_b = _create(client, headers), _create(client, headers)
    reached, release, evidence = _pause_first_batch_select(monkeypatch, batch_a, also_observe=[batch_b])
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_post, client, headers, batch_a, 'close')
        try:
            assert reached.wait(5)
            second = pool.submit(_post, client, headers, batch_b, 'close')
            response = second.result(timeout=5)
            assert response.status_code == 200, response.text
            assert response.json()['data']['batchId'] == batch_b
            assert response.json()['data']['status'] == 'CLOSED'
            first_select, second_select = evidence['selects'][:2]
            assert first_select['batchId'] == batch_a and second_select['batchId'] == batch_b
            assert first_select['connectionId'] != second_select['connectionId']
        finally:
            release.set()
        assert first.result(timeout=5).status_code == 200


def test_registration_batch_scope_and_state_contract_remain_unchanged(client, db_mode):
    del db_mode
    from app.models import AaRegistrationBatch, AffairsAuditTrail
    headers = _headers(client)
    draft_id, open_id = _create(client, headers, opened=False), _create(client, headers)
    assert _post(client, headers, draft_id, 'close').status_code == 409
    assert _post(client, headers, open_id, 'archive').status_code == 409
    student = _headers(client, 'student01')
    assert _post(client, student, open_id, 'close').status_code == 403
    assert _post(client, student, open_id, 'archive').status_code == 403
    with get_sessionmaker()() as db:
        foreign = AaRegistrationBatch(tenant_id=TID + 1, batch_name='T06-foreign-initial', register_type='ANNUAL', status='OPEN')
        deleted = AaRegistrationBatch(tenant_id=TID, batch_name='T06-deleted-initial', register_type='ANNUAL', status='OPEN', is_deleted=True)
        db.add_all([foreign, deleted]); db.commit()
        foreign_id, deleted_id = foreign.id, deleted.id
    for batch_id in [foreign_id, deleted_id]:
        assert _post(client, headers, batch_id, 'close').status_code == 404
        assert _post(client, headers, batch_id, 'archive').status_code == 404
        assert _status(batch_id) == 'OPEN'
    assert _post(client, headers, open_id, 'close').status_code == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _post(client, headers, open_id, 'archive'), range(2)))
    assert all(response.status_code == 200 for response in results), [response.text for response in results]
    assert all(response.json()['data']['batchId'] == open_id and response.json()['data']['status'] == 'ARCHIVED' for response in results)
    assert _status(open_id) == 'ARCHIVED'
    with get_sessionmaker()() as db:
        assert db.query(AffairsAuditTrail).filter_by(tenant_id=TID, biz_type='AA_REG_BATCH', biz_id=int(open_id), action='ARCHIVE').count() == 1
