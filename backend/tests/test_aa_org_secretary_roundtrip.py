"""Secretary binding uses real staff identities and preserves existing workflow owners."""
import importlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from test_aa_orgs_tier1_r2 import BASE, TID, TID2, _hdr, _seed_scoped


def _setup(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import User
    ids = _seed_scoped(db_mode)
    with get_sessionmaker()() as db:
        staff = [User(tenant_id=TID, login_name=f'org_secretary_{n}', real_name=f'秘书验收{n}',
                      password_hash='x', user_type='TEACHER', status='ACTIVE') for n in range(3)]
        db.add_all(staff); db.commit()
        ids['staff'] = [u.id for u in staff]
    return ids, _hdr(client, 'school_admin01'), f"{BASE}/colleges/{ids['colSw']}/secretary"


def test_candidates_are_real_active_staff_and_respect_college_scope(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import User
    ids, headers, url = _setup(client, db_mode)
    with get_sessionmaker()() as db:
        db.add_all([User(tenant_id=tid, login_name=f'org_candidate_{i}', real_name='秘书验收无效', password_hash='x',
                        user_type=kind, status=status) for i, (tid, kind, status) in enumerate([
            (TID2, 'TEACHER', 'ACTIVE'), (TID, 'STUDENT', 'ACTIVE'), (TID, 'GUARDIAN', 'ACTIVE'),
            (TID, 'ENTERPRISE_MENTOR', 'ACTIVE'), (TID, 'PLATFORM_OP', 'ACTIVE'), (TID, 'TEACHER', 'DISABLED')])])
        db.commit()
    result = client.get(f'{url}-candidates', headers=headers, params={'keyword': '秘书验收', 'pageSize': 2}).json()['data']
    assert result['total'] == 3 and len(result['items']) == 2
    exact = client.get(f'{url}-candidates', headers=headers, params={'userId': ids['staff'][2]}).json()['data']['items']
    assert len(exact) == 1 and exact[0]['value'] == str(ids['staff'][2]) and exact[0]['label'] == '秘书验收2'
    college = _hdr(client, 'college_admin01')
    assert client.get(f'{url}-candidates', headers=college).status_code == 200
    assert client.get(f"{BASE}/colleges/{ids['colWl']}/secretary-candidates", headers=college).status_code == 403
    assert client.get(f'{url}-candidates', headers=_hdr(client, 'student01')).status_code == 403


def test_binding_rejects_invalid_identity_and_inactive_college(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, User
    ids, headers, url = _setup(client, db_mode)
    invalid = [('bad', 400), ('-1', 400), ('999999999', 404)]
    with get_sessionmaker()() as db:
        for n, (tid, kind, status, deleted, expected) in enumerate([
            (TID2, 'TEACHER', 'ACTIVE', False, 404), (TID, 'TEACHER', 'ACTIVE', True, 404),
            (TID, 'TEACHER', 'DISABLED', False, 400), (TID, 'STUDENT', 'ACTIVE', False, 400),
            (TID, 'GUARDIAN', 'ACTIVE', False, 400), (TID, 'ENTERPRISE_MENTOR', 'ACTIVE', False, 400),
            (TID, 'PLATFORM_OP', 'ACTIVE', False, 400)]):
            user = User(tenant_id=tid, login_name=f'invalid_secretary_{n}', real_name='不适用账号', password_hash='x',
                        user_type=kind, status=status, is_deleted=deleted)
            db.add(user); db.flush(); invalid.append((str(user.id), expected))
        db.commit()
    for sid, expected in invalid:
        assert client.post(url, headers=headers, json={'secretaryId': sid, 'expectedVersion': 0}).status_code == expected
    with get_sessionmaker()() as db:
        college = db.get(College, ids['colSw'])
        assert college.secretary_id is None and college.version == 0
        college.status = 'DISABLED'; db.commit()
    assert client.post(url, headers=headers, json={'secretaryId': str(ids['staff'][0])}).status_code == 400
    assert client.post(url, headers=headers, json={'secretaryId': None}).status_code == 200


def test_binding_versions_names_idempotence_and_unbinding_history(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail, User
    ids, headers, url = _setup(client, db_mode)
    body = {'secretaryId': str(ids['staff'][0]), 'expectedVersion': 0}
    first = client.post(url, headers=headers, json=body).json()['data']
    assert first['version'] == 1 and first['secretaryName'] == '秘书验收0' and first['secretaryStatus'] == 'ACTIVE'
    assert client.post(url, headers=headers, json=body).status_code == 409
    assert client.post(url, headers=headers, json={'secretaryId': body['secretaryId']}).json()['data']['version'] == 1
    with get_sessionmaker()() as db:
        db.get(User, ids['staff'][0]).status = 'DISABLED'; db.commit()
    current = next(r for r in client.get(f'{BASE}/colleges', headers=headers).json()['data']['items'] if r['id'] == str(ids['colSw']))
    assert current['secretaryName'] == '秘书验收0' and current['secretaryStatus'] == 'DISABLED'
    cleared = client.post(url, headers=headers, json={'secretaryId': None, 'expectedVersion': 1}).json()['data']
    assert cleared['secretaryId'] is None and cleared['secretaryName'] is None and cleared['version'] == 2
    assert client.post(url, headers=headers, json={'secretaryId': None}).json()['data']['version'] == 2
    with get_sessionmaker()() as db:
        audits = db.scalars(select(AffairsAuditTrail).where(AffairsAuditTrail.biz_type == 'AA_ORG_COLLEGE',
            AffairsAuditTrail.biz_id == ids['colSw'], AffairsAuditTrail.action == 'BIND_SECRETARY').order_by(AffairsAuditTrail.id)).all()
        assert len(audits) == 2 and '秘书验收0' in audits[1].before_val


def test_concurrent_binding_has_one_winner(client, db_mode):
    ids, headers, url = _setup(client, db_mode)
    barrier = Barrier(2)
    def bind(sid):
        barrier.wait(timeout=10)
        return client.post(url, headers=headers, json={'secretaryId': str(sid), 'expectedVersion': 0})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(bind, ids['staff'][:2]))
    assert sorted(r.status_code for r in results) == [200, 409]


def test_binding_audit_failure_is_atomic_and_cross_college_write_is_denied(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import College
    ids, headers, url = _setup(client, db_mode)
    assert client.post(f"{BASE}/colleges/{ids['colWl']}/secretary", headers=_hdr(client, 'college_admin01'),
                       json={'secretaryId': str(ids['staff'][0])}).status_code == 403
    svc = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service')
    def fail(*args, **kwargs):
        raise RuntimeError('secretary audit failure')
    monkeypatch.setattr(svc, '_audit', fail)
    with pytest.raises(RuntimeError, match='secretary audit failure'):
        client.post(url, headers=headers, json={'secretaryId': str(ids['staff'][0]), 'expectedVersion': 0})
    with get_sessionmaker()() as db:
        c = db.get(College, ids['colSw'])
        assert c.secretary_id is None and c.version == 0


def test_binding_changes_future_resolvers_but_preserves_assignments_permissions_and_pending_owner(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import Permission, Role, RolePermission, StaffAssignment, UserRole, WorkflowInstance, WorkflowTask
    from app.core.exceptions import AppException
    ids, headers, url = _setup(client, db_mode)
    guard = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_grade_task_assignee_guard')
    correction = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_grade_correction_command')
    monkeypatch.setattr(guard._core, '_tid', lambda: TID)
    monkeypatch.setattr(correction, '_tid', lambda: TID)
    old, new, plain = ids['staff']
    with get_sessionmaker()() as db:
        role = Role(tenant_id=TID, role_code='ORG_SECRETARY_REVIEW_TEST', role_name='组织验收审核岗位', role_type='CUSTOM', status='ACTIVE')
        db.add(role); db.flush()
        for code in ['academicAffairs.grade.collegeReview', 'academicAffairs.scheduleChange.collegeReview', 'academicAffairs.gradeChange.review']:
            p = db.scalar(select(Permission).where(Permission.permission_code == code))
            assert p is not None
            db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=p.id, status='ACTIVE'))
        db.add_all([UserRole(tenant_id=TID, user_id=uid, role_id=role.id, status='ACTIVE') for uid in [old, new]])
        db.add(StaffAssignment(tenant_id=TID, user_id=old, org_type='COLLEGE', org_node_id=ids['colSw'],
            assignment_type='SECRETARY', is_primary=True, source_type='MANUAL', effective_at=datetime.utcnow() - timedelta(days=1), status='ACTIVE'))
        instance = WorkflowInstance(tenant_id=TID, workflow_code='ORG_TEST_GRADE_CHANGE', source_module='academic-affairs',
            source_biz_type='AA_GRADE_CHANGE', source_biz_id=123, applicant_id=plain, current_node='COLLEGE_REVIEW', status='RUNNING')
        db.add(instance); db.flush()
        pending = WorkflowTask(tenant_id=TID, instance_id=instance.id, node_code='COLLEGE_REVIEW', assignee_id=old, status='PENDING')
        db.add(pending); db.commit(); instance_id, pending_id = instance.id, pending.id
        role_count = db.scalar(select(func.count()).select_from(UserRole))
        assignment_count = db.scalar(select(func.count()).select_from(StaffAssignment))
    def resolve_all(expected):
        with get_sessionmaker()() as db:
            task = SimpleNamespace(class_id=ids['c1'])
            assert guard.resolve_grade_task_assignee(db, 'COLLEGE_REVIEW', task) == expected
            assert guard.resolve_grade_task_assignee(db, 'COLLEGE_REVIEW', task, college_perm=guard.SCHEDULE_CHANGE_COLLEGE_PERM) == expected
            assert correction.resolve_change_assignee(db, 'COLLEGE_REVIEW', task) == expected
    assert client.post(url, headers=headers, json={'secretaryId': str(new), 'expectedVersion': 0}).status_code == 200
    resolve_all(new)
    with get_sessionmaker()() as db:
        assert db.get(WorkflowTask, pending_id).assignee_id == old
        monkeypatch.setattr(correction, '_current_user_id', lambda db: old)
        assert correction._claim_task(db, SimpleNamespace(workflow_instance_id=instance_id), 'COLLEGE_REVIEW')[1].id == pending_id
        monkeypatch.setattr(correction, '_current_user_id', lambda db: new)
        with pytest.raises(AppException) as rejected:
            correction._claim_task(db, SimpleNamespace(workflow_instance_id=instance_id), 'COLLEGE_REVIEW')
        assert rejected.value.http_status == 403
    assert client.post(url, headers=headers, json={'secretaryId': str(plain), 'expectedVersion': 1}).status_code == 200
    resolve_all(old)  # A binding cannot grant review permission; the existing valid appointment remains authoritative.
    assert client.post(url, headers=headers, json={'secretaryId': None, 'expectedVersion': 2}).status_code == 200
    resolve_all(old)
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(UserRole)) == role_count
        assert db.scalar(select(func.count()).select_from(StaffAssignment)) == assignment_count
        assert db.get(WorkflowTask, pending_id).assignee_id == old
