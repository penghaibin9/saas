"""Additive storage keeps complete evidence and fails closed for N-1 writers."""
import json
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_org_adjustment_storage as storage


def row(**values):
    defaults = dict(status='DRAFT', from_class_ids='[1]',
        from_class_ids_expanded=None, check_result_json=None, check_result_expanded=None)
    return SimpleNamespace(**(defaults | values))


def test_small_receipt_is_compatible_with_legacy_readers():
    r = row(); payload = {'blocked': False, 'refs': [{'classId': '1'}]}
    storage.store_check(r, payload)
    assert json.loads(r.check_result_json) == payload
    assert storage.read_check(r) == payload


def test_large_receipt_preserves_all_rows_and_legacy_projection_is_not_an_approval():
    r = row(); payload = {'blocked': False, 'refs': [{'classId': str(i), 'name': '完整核对证据' * 20} for i in range(30)]}
    storage.store_check(r, payload)
    assert len(r.check_result_json) <= 2000
    assert json.loads(r.check_result_json)['blocked'] is True
    assert storage.read_check(r) == payload


def test_legacy_write_invalidates_expanded_receipt_instead_of_replaying_old_success():
    r = row(); storage.store_check(r, {'blocked': False, 'snapshotHash': 'prior'})
    r.check_result_json = json.dumps({'blocked': True, 'snapshotHash': 'new'})
    assert storage.read_check(r) == {'blocked': True, 'snapshotHash': 'new'}


@pytest.mark.parametrize('content', ['{', '[]', '{"schemaVersion":99}'])
def test_corrupt_expansion_fails_closed(content):
    r = row(); r.check_result_expanded = content
    with pytest.raises(AppException): storage.read_check(r)


def test_expanded_scope_keeps_legacy_state_guards_closed_through_all_transitions():
    r = row(); r.from_class_ids_expanded = json.dumps(list(range(1, 501)))
    for state in ('DRAFT', 'CHECKED', 'EXECUTED', 'CANCELLED'):
        storage.set_status(r, state)
        assert r.status == 'V2_' + state
        assert r.status not in ('DRAFT', 'CHECKED', 'EXECUTED', 'CANCELLED')
        assert storage.public_status(r) == state
        assert len(json.loads(storage.scope_json(r))) == 500


def test_missing_expanded_scope_never_falls_back_to_an_empty_legacy_scope():
    r = row(); r.status = 'V2_CHECKED'
    with pytest.raises(AppException): storage.scope_json(r)


def test_model_retains_legacy_varchar_contract_and_nullable_expansion():
    from app.models import AaClassAdjustmentRequest
    columns = AaClassAdjustmentRequest.__table__.c
    assert columns.from_class_ids.type.length == 500
    assert columns.check_result_json.type.length == 2000
    assert columns.from_class_ids_expanded.nullable
    assert columns.check_result_expanded.nullable


def test_expanded_request_uses_complete_scope_on_real_http_and_mysql(client, db_mode):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import AaClassAdjustmentRequest, SchoolClass
    from test_aa_org_adjustment_roundtrip import _create, _act
    from test_aa_orgs import TID, _hdr
    from test_aa_orgs_tier1_r2 import _seed_scoped
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    sources = [900000000000005000 + i for i in range(30)]
    with get_sessionmaker()() as db:
        db.add_all([SchoolClass(id=cid, tenant_id=TID, major_id=ids['majSw'],
            class_name=f'扩展兼容验收{i}', class_status='NORMAL', status='ACTIVE') for i, cid in enumerate(sources)])
        db.commit()
    created = _create(client, headers, sources)
    assert set(created['fromClassIds']) == {str(cid) for cid in sources}
    checked = _act(client, headers, created, 'precheck')
    assert checked.status_code == 200, checked.text
    assert len(checked.json()['data']['checkResult']['refs']) == 30
    with get_sessionmaker()() as db:
        persisted = db.scalar(select(AaClassAdjustmentRequest).where(
            AaClassAdjustmentRequest.id == int(created['id']), AaClassAdjustmentRequest.tenant_id == TID))
        assert persisted.status == 'V2_CHECKED'
        assert len(persisted.from_class_ids) <= 500
        assert json.loads(persisted.from_class_ids_expanded) == sources
        assert json.loads(persisted.check_result_json)['blocked'] is True
    executed = _act(client, headers, created, 'execute', expectedVersion=checked.json()['data']['version'])
    assert executed.status_code == 200, executed.text
    assert executed.json()['data']['status'] == 'EXECUTED'
    assert executed.json()['data']['checkResult']['execution']['changedClassCount'] == 30
