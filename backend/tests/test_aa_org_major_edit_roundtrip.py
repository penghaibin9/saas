"""Major editing must keep authorization, version, master and audit in one transaction."""
import importlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select

from test_aa_orgs import BASE, TID, _hdr, _mk_major
from test_aa_orgs_tier1_r2 import _seed_scoped


def _audit_count(db, model, major_id):
    if model.__name__ == 'SecurityAuditLog':
        conditions = [model.action == 'ORG_NODE_SAVE', model.resource == f'MAJOR:{major_id}']
    else:
        conditions = [model.biz_type == 'AA_ORG_MAJOR', model.biz_id == major_id, model.action == 'UPDATE']
    return db.scalar(select(func.count()).select_from(model).where(model.tenant_id == TID, *conditions))


@pytest.mark.parametrize('failure', ['business', 'master'])
def test_major_audit_failure_rolls_back_every_write(client, db_mode, monkeypatch, failure):
    from app.db.session import get_sessionmaker
    from app.models import Major, AffairsAuditTrail, SecurityAuditLog
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    svc = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service')
    audit_service = importlib.import_module('app.services.db_service')
    with get_sessionmaker()() as db:
        row = db.get(Major, ids['majSw'])
        before = (row.major_name, row.college_id, row.version, row.remark)
        counts = [_audit_count(db, model, row.id) for model in (AffairsAuditTrail, SecurityAuditLog)]
    def fail(*args, **kwargs):
        raise RuntimeError('major audit unavailable')
    if failure == 'business':
        monkeypatch.setattr(svc, '_audit', fail)
    else:
        monkeypatch.setattr(audit_service, 'audit_insert_in_session', fail)
    with pytest.raises(RuntimeError, match='major audit unavailable'):
        client.put(f"{BASE}/majors/{ids['majSw']}", headers=headers,
                   json={'majorName': '不应保存的专业名称', 'remark': '事务回滚验收', 'expectedVersion': before[2]})
    with get_sessionmaker()() as db:
        row = db.get(Major, ids['majSw'])
        assert (row.major_name, row.college_id, row.version, row.remark) == before
        assert [_audit_count(db, model, row.id) for model in (AffairsAuditTrail, SecurityAuditLog)] == counts


def test_major_scope_uses_locked_current_parent(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import Major
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'college_admin01')
    svc = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service')
    original = svc._get_major
    moved = False
    def stale_then_move(db, mid, **kwargs):
        nonlocal moved
        # Only the unlocked legacy read is stale. The revised writer must request
        # the locking read, which is simulated after this competing commit.
        if kwargs.get('for_update'):
            with get_sessionmaker()() as other:
                other.get(Major, ids['majSw']).college_id = ids['colWl']
                other.commit()
            moved = True
            return original(db, mid, **kwargs)
        result = original(db, mid)
        if not moved:
            with get_sessionmaker()() as other:
                other.get(Major, ids['majSw']).college_id = ids['colWl']
                other.commit()
            moved = True
        return result
    monkeypatch.setattr(svc, '_get_major', stale_then_move)
    response = client.put(f"{BASE}/majors/{ids['majSw']}", headers=headers,
                          json={'majorName': '越范围修改名称'})
    assert response.status_code == 403, response.text
    with get_sessionmaker()() as db:
        assert db.get(Major, ids['majSw']).major_name != '越范围修改名称'


def test_major_concurrent_edits_one_version_and_audit(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Major, AffairsAuditTrail, SecurityAuditLog
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    barrier = Barrier(2)
    def save(name):
        barrier.wait(timeout=10)
        return client.put(f"{BASE}/majors/{ids['majSw']}", headers=headers,
                          json={'majorName': name, 'expectedVersion': 0})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(save, name) for name in ('并发专业甲', '并发专业乙')]
        results = [future.result(timeout=30) for future in futures]
    assert sorted(result.status_code for result in results) == [200, 409], [r.text for r in results]
    with get_sessionmaker()() as db:
        assert db.get(Major, ids['majSw']).version == 1
        assert _audit_count(db, AffairsAuditTrail, ids['majSw']) == 1
        assert _audit_count(db, SecurityAuditLog, ids['majSw']) == 1


def test_empty_major_parent_edit_preserves_legacy_contract_and_audit_reason(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Major, AffairsAuditTrail, SecurityAuditLog
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    major = _mk_major(client, headers, str(ids['colSw']), name='空专业', code='ATOMIC_EMPTY')
    result = client.put(f"{BASE}/majors/{major['id']}", headers=headers,
                        json={'collegeId': str(ids['colWl']), 'reason': '空专业归属纠正验收', 'expectedVersion': 0})
    assert result.status_code == 200, result.text
    assert result.json()['data']['collegeId'] == str(ids['colWl'])
    with get_sessionmaker()() as db:
        row = db.get(Major, int(major['id']))
        assert row.version == 1 and row.code == 'ATOMIC_EMPTY'
        audit = db.scalar(select(AffairsAuditTrail).where(AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_id == row.id, AffairsAuditTrail.biz_type == 'AA_ORG_MAJOR',
            AffairsAuditTrail.action == 'UPDATE'))
        assert '空专业归属纠正验收' in audit.detail
        assert _audit_count(db, SecurityAuditLog, row.id) == 2  # create + edit


@pytest.mark.parametrize('operation', ['create', 'delete'])
@pytest.mark.parametrize('failure', ['business', 'master'])
def test_major_create_delete_also_roll_back_with_audit(client, db_mode, monkeypatch, operation, failure):
    from app.db.session import get_sessionmaker
    from app.models import Major, AffairsAuditTrail, SecurityAuditLog
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    row = _mk_major(client, headers, str(ids['colSw']), name='软删除回滚验收', code='MAJOR_DELETE_ROLLBACK')
    svc = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service')
    audit_service = importlib.import_module('app.services.db_service')
    with get_sessionmaker()() as db:
        before = [db.scalar(select(func.count()).select_from(model).where(model.tenant_id == TID))
                  for model in (Major, AffairsAuditTrail, SecurityAuditLog)]
    def fail(*args, **kwargs):
        raise RuntimeError('major operation audit unavailable')
    monkeypatch.setattr(svc if failure == 'business' else audit_service,
                        '_audit' if failure == 'business' else 'audit_insert_in_session', fail)
    with pytest.raises(RuntimeError, match='major operation audit unavailable'):
        if operation == 'create':
            client.post(f'{BASE}/majors', headers=headers,
                        json={'majorName': '新建回滚验收', 'collegeId': str(ids['colSw']), 'code': 'MAJOR_CREATE_ROLLBACK'})
        else:
            client.delete(f"{BASE}/majors/{row['id']}", headers=headers)
    with get_sessionmaker()() as db:
        assert not db.get(Major, int(row['id'])).is_deleted
        assert db.get(Major, int(row['id'])).version == 0
        assert [db.scalar(select(func.count()).select_from(model).where(model.tenant_id == TID))
                for model in (Major, AffairsAuditTrail, SecurityAuditLog)] == before
