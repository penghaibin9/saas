"""College maintenance keeps existing scope, secretary and audits consistent."""
import importlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select

from test_aa_orgs import BASE, TID, _hdr, _mk_college
from test_aa_orgs_tier1_r2 import _seed_scoped


def _counts(db):
    from app.models import College, AffairsAuditTrail, SecurityAuditLog
    return [db.scalar(select(func.count()).select_from(model).where(model.tenant_id == TID))
            for model in (College, AffairsAuditTrail, SecurityAuditLog)]


@pytest.mark.parametrize('operation', ['create', 'update', 'delete'])
@pytest.mark.parametrize('failure', ['business', 'master'])
def test_college_audit_failure_rolls_back_operation(client, db_mode, monkeypatch, operation, failure):
    from app.db.session import get_sessionmaker
    from app.models import College, TeacherStudentScope
    headers = _hdr(client, 'school_admin01')
    college = _mk_college(client, headers, '学院事务验收', 'COLLEGE_ATOMIC')
    with get_sessionmaker()() as db:
        scope = TeacherStudentScope(tenant_id=TID, teacher_key='college_atomic_scope',
            scope_type='COLLEGE', ref_value='学院事务验收', status='ACTIVE')
        db.add(scope); db.commit(); scope_id = scope.id
        before = _counts(db)
    target = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service'
                                    if failure == 'business' else 'app.services.db_service')
    def fail(*args, **kwargs):
        raise RuntimeError('college audit unavailable')
    monkeypatch.setattr(target, '_audit' if failure == 'business' else 'audit_insert_in_session', fail)
    with pytest.raises(RuntimeError, match='college audit unavailable'):
        if operation == 'create':
            client.post(f'{BASE}/colleges', headers=headers, json={'collegeName': '创建后应回滚', 'code': 'COLLEGE_ROLLBACK'})
        elif operation == 'update':
            client.put(f"{BASE}/colleges/{college['id']}", headers=headers,
                       json={'collegeName': '更名后应回滚', 'expectedVersion': 0})
        else:
            client.delete(f"{BASE}/colleges/{college['id']}", headers=headers)
    with get_sessionmaker()() as db:
        row = db.get(College, int(college['id']))
        assert row.college_name == '学院事务验收' and row.version == 0 and not row.is_deleted
        assert db.get(TeacherStudentScope, scope_id).ref_value == '学院事务验收'
        assert _counts(db) == before


def test_college_rename_preserves_the_same_scoped_students(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, TeacherStudentScope, StudentProfile, RoleAssignmentScope, Role, User, UserRole
    from app.models.academic_affairs_student_fact import StudentAcademicFact
    ids = _seed_scoped(db_mode)
    scoped = _hdr(client, 'college_admin01')
    before_visible = client.get(f'{BASE}/classes', headers=scoped).json()['data']['items']
    with get_sessionmaker()() as db:
        user = User(tenant_id=TID, login_name='college_stable_id_user', real_name='稳定授权验收',
                    user_type='TEACHER', password_hash='x', status='ACTIVE')
        role = Role(tenant_id=TID, role_code='COLLEGE_STABLE_TEST', role_name='稳定授权验收', role_type='CUSTOM', status='ACTIVE')
        db.add_all([user, role]); db.flush()
        membership = UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status='ACTIVE')
        db.add(membership); db.flush()
        db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=membership.id, user_id=user.id,
            role_code=role.role_code, scope_type='COLLEGE', scope_id=ids['colSw'], scope_name_snapshot='软件学院'))
        foreign = TeacherStudentScope(tenant_id=TID + 1, teacher_key='foreign_college_scope',
            scope_type='COLLEGE', ref_value='软件学院', status='ACTIVE')
        db.add(foreign); db.commit(); foreign_id = foreign.id
        facts = [(r.id, r.college_id, r.version_no, r.valid_to) for r in db.scalars(
            select(StudentAcademicFact).where(StudentAcademicFact.tenant_id == TID)).all()]
        students = [(r.id, r.college_id, r.version) for r in db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == TID)).all()]
        stable = [(r.id, r.scope_id, r.version) for r in db.scalars(select(RoleAssignmentScope).where(RoleAssignmentScope.tenant_id == TID)).all()]
        inactive = TeacherStudentScope(tenant_id=TID, teacher_key='college_inactive_scope',
            scope_type='COLLEGE', ref_value='软件学院', status='INACTIVE')
        deleted = TeacherStudentScope(tenant_id=TID, teacher_key='college_deleted_scope',
            scope_type='COLLEGE', ref_value='软件学院', status='ACTIVE', is_deleted=True)
        db.add_all([inactive, deleted]); db.commit(); inactive_id, deleted_id = inactive.id, deleted.id
    result = client.put(f"{BASE}/colleges/{ids['colSw']}", headers=_hdr(client, 'school_admin01'),
                        json={'collegeName': '软件工程学院', 'expectedVersion': 0})
    assert result.status_code == 200, result.text
    after_visible = client.get(f'{BASE}/classes', headers=scoped).json()['data']['items']
    assert {r['id'] for r in after_visible} == {r['id'] for r in before_visible}
    assert str(ids['cWl']) not in {r['id'] for r in after_visible}
    assert client.put(f"{BASE}/colleges/{ids['colSw']}", headers=scoped, json={'shortName': '软工'}).status_code == 200
    assert client.put(f"{BASE}/colleges/{ids['colWl']}", headers=scoped, json={'shortName': '越权'}).status_code == 403
    with get_sessionmaker()() as db:
        assert db.get(College, ids['colSw']).short_name == '软工'
        assert db.get(TeacherStudentScope, inactive_id).ref_value == '软件工程学院'
        assert db.get(TeacherStudentScope, inactive_id).status == 'INACTIVE'
        assert db.get(TeacherStudentScope, deleted_id).ref_value == '软件学院'
        assert db.get(TeacherStudentScope, foreign_id).ref_value == '软件学院'
        assert [(r.id, r.college_id, r.version_no, r.valid_to) for r in db.scalars(select(StudentAcademicFact).where(StudentAcademicFact.tenant_id == TID)).all()] == facts
        assert [(r.id, r.college_id, r.version) for r in db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == TID)).all()] == students
        assert [(r.id, r.scope_id, r.version) for r in db.scalars(select(RoleAssignmentScope).where(RoleAssignmentScope.tenant_id == TID)).all()] == stable


@pytest.mark.parametrize('ambiguity', ['source', 'destination', 'orphan'])
def test_college_rename_refuses_ambiguous_name_scope(client, db_mode, ambiguity):
    from app.db.session import get_sessionmaker
    from app.models import College, TeacherStudentScope
    ids = _seed_scoped(db_mode)
    name = '网络学院' if ambiguity == 'destination' else '新学院'
    with get_sessionmaker()() as db:
        if ambiguity == 'source':
            db.add(College(tenant_id=TID, college_name='软件学院', status='ACTIVE'))
        elif ambiguity == 'orphan':
            db.add(TeacherStudentScope(tenant_id=TID, teacher_key='orphan_scope', scope_type='COLLEGE', ref_value=name, status='ACTIVE'))
        db.commit()
    response = client.put(f"{BASE}/colleges/{ids['colSw']}", headers=_hdr(client, 'school_admin01'),
                          json={'collegeName': name, 'expectedVersion': 0})
    assert response.status_code == 409, response.text
    with get_sessionmaker()() as db:
        assert db.get(College, ids['colSw']).college_name == '软件学院'
        assert db.get(College, ids['colSw']).version == 0


def test_college_edit_and_secretary_binding_share_one_version(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, User, AffairsAuditTrail
    headers = _hdr(client, 'school_admin01')
    college = _mk_college(client, headers, '绑定并发学院', 'COLLEGE_CONCURRENT')
    with get_sessionmaker()() as db:
        teacher = User(tenant_id=TID, login_name='college_concurrent_teacher', real_name='验收秘书',
                       user_type='TEACHER', status='ACTIVE', password_hash='x')
        db.add(teacher); db.commit(); user_id = teacher.id
    barrier = Barrier(2)
    def edit():
        barrier.wait(timeout=10)
        return client.put(f"{BASE}/colleges/{college['id']}", headers=headers,
                          json={'shortName': '并发简称', 'expectedVersion': 0})
    def bind():
        barrier.wait(timeout=10)
        return client.post(f"{BASE}/colleges/{college['id']}/secretary", headers=headers,
                           json={'secretaryId': str(user_id), 'expectedVersion': 0})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(edit), pool.submit(bind)]
        responses = [future.result(timeout=30) for future in futures]
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    with get_sessionmaker()() as db:
        row = db.get(College, int(college['id']))
        assert row.version == 1
        changes = db.scalars(select(AffairsAuditTrail).where(AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == 'AA_ORG_COLLEGE', AffairsAuditTrail.biz_id == row.id,
            AffairsAuditTrail.action.in_(['UPDATE', 'BIND_SECRETARY']))).all()
        assert len(changes) == 1
    stale = client.put(f"{BASE}/colleges/{college['id']}", headers=headers,
                       json={'collegeName': '过期名称', 'expectedVersion': 0})
    assert stale.status_code == 409
    assert stale.json()['details']['reason'] == 'VERSION_CONFLICT'


def test_college_field_limits_and_legacy_scope_name_capacity(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, TeacherStudentScope
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    for field, value in [('collegeName', '院' * 201), ('shortName', '简' * 101),
                         ('code', 'X' * 51), ('sortOrder', 2147483648), ('remark', '注' * 501)]:
        response = client.put(f"{BASE}/colleges/{ids['colSw']}", headers=headers, json={field: value})
        assert response.status_code == 400, response.text  # Repository validation handler uses HTTP 400.
        assert response.json()['bizCode'] == 'VALIDATION_ERROR' and response.json()['details']
    too_long = client.put(f"{BASE}/colleges/{ids['colSw']}", headers=headers,
                          json={'collegeName': '院' * 129, 'expectedVersion': 0})
    assert too_long.status_code == 400, too_long.text
    # Names longer than the legacy scope field remain valid for colleges with no
    # such mappings; the schema itself permits 200 characters.
    plain = _mk_college(client, headers, '无历史授权学院', 'COLLEGE_LONG')
    assert client.put(f"{BASE}/colleges/{plain['id']}", headers=headers, json={'collegeName': '院' * 129}).status_code == 200
    with get_sessionmaker()() as db:
        assert db.get(College, ids['colSw']).college_name == '软件学院'
        assert db.scalar(select(TeacherStudentScope).where(TeacherStudentScope.tenant_id == TID,
            TeacherStudentScope.teacher_key == 'college_admin01')).ref_value == '软件学院'
