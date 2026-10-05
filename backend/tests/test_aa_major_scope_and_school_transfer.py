"""T07：无班级专业范围及正式学院撤岗后的校级责任，独立 MySQL 回归。"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import academic_affairs_program_service as programs
from app.modules.academic_affairs.services import academic_affairs_responsibility_service as responsibility
from app.services import organization_version_service as appointments

TID = 1000000000000000886
OTHER_TID = 1000000000000000887


@pytest.fixture
def facts(db_mode):
    """只准备隔离业务前置；角色权限来自真实 UserRole/RolePermission，不替换 guard。"""
    from app.models import (AaProgram, College, Major, Role, RoleAssignmentScope,
                            RolePermission, SchoolClass, Tenant, User, UserRole)
    from tests.support_academic_review_identity import _ensure_permission

    previous_tenant, previous_user = get_tenant(), get_current_user_ctx()
    set_tenant(TID)
    with get_sessionmaker()() as db:
        for tid, code in ((TID, 'aa-major-transfer'), (OTHER_TID, 'aa-major-transfer-other')):
            if db.get(Tenant, tid) is None:
                db.add(Tenant(id=tid, tenant_code=code, school_name='隔离教务范围学校',
                              short_name='教务范围', deploy_mode='SAAS', db_mode='SHARED', status='ACTIVE'))
        db.flush()
        college = College(tenant_id=TID, college_name='专业范围学院', code='MAJOR-TRANSFER', status='ACTIVE')
        foreign_college = College(tenant_id=OTHER_TID, college_name='另一学校学院', status='ACTIVE')
        db.add_all([college, foreign_college]); db.flush()
        own = Major(tenant_id=TID, college_id=college.id, major_name='尚无班级专业', code='EMPTY-MAJOR', status='ACTIVE')
        sibling = Major(tenant_id=TID, college_id=college.id, major_name='同院其他专业', code='SIBLING-MAJOR', status='ACTIVE')
        foreign = Major(tenant_id=OTHER_TID, college_id=foreign_college.id, major_name='另一学校专业', status='ACTIVE')
        db.add_all([own, sibling, foreign]); db.flush()
        sibling_class = SchoolClass(tenant_id=TID, major_id=sibling.id, class_name='其他专业班级', status='ACTIVE')
        db.add(sibling_class)
        program_ids = {}
        for label, major in (('own', own), ('sibling', sibling), ('foreign', foreign)):
            row = AaProgram(tenant_id=major.tenant_id, major_id=major.id, program_name=f'{label}方案',
                            series_key=f'T07-{label}', grade_year='2098', total_credits=100, version=1, status='DRAFT')
            db.add(row); db.flush(); program_ids[label] = row.id

        def identity(login, role_code, permission_codes, scope_type, scope_id):
            person = User(tenant_id=TID, login_name=login, real_name='隔离责任人',
                          user_type='TEACHER', password_hash='unused-in-service-test', status='ACTIVE')
            role = Role(tenant_id=TID, role_code=role_code, role_name='教务回归责任岗位', role_type='CUSTOM', status='ACTIVE')
            db.add_all([person, role]); db.flush()
            link = UserRole(tenant_id=TID, user_id=person.id, role_id=role.id, status='ACTIVE')
            db.add(link); db.flush()
            for code in permission_codes:
                permission = _ensure_permission(db, code)
                db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status='ACTIVE'))
            scope = RoleAssignmentScope(tenant_id=TID, user_role_id=link.id, user_id=person.id,
                role_code=role_code, scope_type=scope_type, scope_id=scope_id, status='ACTIVE',
                effective_at=datetime(2020, 1, 1))
            db.add(scope); db.flush()
            claim = dict(userId=str(person.id), loginName=login, userType='TEACHER',
                         tenantId=str(TID), currentRoleCode=role_code, activeContextId=f'role:{role.id}')
            return claim, scope.id, role.id

        major_user, scope_id, _ = identity('t07-major-owner', 'V5_PROGRAM_MAJOR_OWNER',
            ('academicAffairs.program.view', 'academicAffairs.program.manage'), 'MAJOR', own.id)
        school_user, _, school_role = identity('t07-school-reviewer', 'V5_PROGRAM_SCHOOL_REVIEWER',
            ('academicAffairs.program.view', 'academicAffairs.program.review'), 'SCHOOL', TID)
        college.secretary_id = int(school_user['userId'])
        db.commit()
        data = dict(college=college.id, major=own.id, sibling=sibling.id, foreign=foreign.id,
                    sibling_class=sibling_class.id, programs=program_ids, scope=scope_id,
                    major_user=major_user, school_user=school_user, school_role=school_role)
    try:
        set_current_user(major_user)
        appointments.create_assignment(user_id=int(major_user['userId']), org_type='MAJOR',
            org_node_id=data['major'], assignment_type='LEADER', tenant_id=TID,
            effective_at=datetime(2020, 1, 1), reason='隔离专业编制岗位')
        yield data
    finally:
        set_current_user(previous_user)
        set_tenant(previous_tenant)


def _program_body(major_id, name='本专业新方案'):
    return SimpleNamespace(programName=name, majorId=str(major_id), gradeYear='2099',
                           totalCredits=100, requirement={})


def _denied(call):
    with pytest.raises(AppException) as error:
        call()
    assert error.value.code in {'NO_DATA_SCOPE', 'DATA_NOT_FOUND'}


def test_empty_major_can_read_and_compile_without_expanding_student_or_sibling_scope(facts):
    from app.core.affairs_security import build_affairs_context, student_directory_scope
    from app.models import SchoolClass
    from app.modules.academic_affairs.services import academic_affairs_flow_service as flow

    user = facts['major_user']
    with get_sessionmaker()() as db:
        assert db.scalar(select(SchoolClass.id).where(SchoolClass.tenant_id == TID,
            SchoolClass.major_id == facts['major'])) is None
        context = build_affairs_context(user, db)
        assert context.scope_type == 'CLASS' and context.is_scope_configured
        assert context.major_ids == {facts['major']}
        assert context.class_ids == set() and context.college_ids == set()
    assert student_directory_scope(user) == (set(), None)
    own = programs.get_program(facts['programs']['own'], user)
    assert own['responsibility']['assigneeUserIds'] == [user['userId']]
    assert own['responsibility']['resolved'] is True
    edited = programs.update_program(facts['programs']['own'], user,
                                     SimpleNamespace(programName='本专业已编辑方案'))
    assert edited['programName'] == '本专业已编辑方案'
    created = programs.create_program(_program_body(facts['major']), user)
    assert programs.get_program(created['programId'], user)['majorId'] == str(facts['major'])
    for target in ('sibling', 'foreign'):
        _denied(lambda: programs.get_program(facts['programs'][target], user))
        _denied(lambda: programs.update_program(facts['programs'][target], user,
            SimpleNamespace(programName='不可写入')))
        _denied(lambda: programs.create_program(_program_body(facts[target]), user))
    assert student_directory_scope(user) == (set(), None)
    assert programs.get_program(facts['programs']['own'], user)['programName'] == '本专业已编辑方案'
    projection = flow.flow(user)
    assert projection['viewer']['majorIds'] == [str(facts['major'])]
    assert projection['viewer']['collegeIds'] == []
    assert projection['unitProgress'] == [] and projection['schoolGates'] == []
    assert projection['stages'][2]['evidence']['programCount'] == 2
    _denied(lambda: flow.flow(user, college_id=facts['college']))


@pytest.mark.parametrize('invalid', ['revoked', 'expired', 'scope_deleted', 'major_deleted', 'major_disabled', 'foreign_major'])
def test_empty_major_invalid_scope_cannot_read_or_compile(facts, invalid):
    from app.core.affairs_security import build_affairs_context, student_directory_scope
    from app.models import Major, RoleAssignmentScope

    with get_sessionmaker()() as db:
        scope = db.get(RoleAssignmentScope, facts['scope'])
        if invalid == 'revoked':
            scope.status = 'REVOKED'
        elif invalid == 'expired':
            scope.expires_at = datetime.utcnow() - timedelta(days=1)
        elif invalid == 'scope_deleted':
            scope.is_deleted = True
        elif invalid == 'major_deleted':
            db.get(Major, facts['major']).is_deleted = True
        elif invalid == 'major_disabled':
            db.get(Major, facts['major']).status = 'DISABLED'
        else:
            scope.scope_id = facts['foreign']
        db.commit()
    user = facts['major_user']
    with get_sessionmaker()() as db:
        context = build_affairs_context(user, db)
        assert context.major_ids == set()
        assert context.class_ids == set() and context.college_ids == set()
    _denied(lambda: programs.get_program(facts['programs']['own'], user))
    _denied(lambda: programs.update_program(facts['programs']['own'], user,
        SimpleNamespace(programName='不可写入')))
    _denied(lambda: programs.create_program(_program_body(facts['major']), user))
    assert student_directory_scope(user) == (set(), None)


@pytest.mark.parametrize('invalid', ['disabled', 'deleted'])
@pytest.mark.parametrize('only_invalid', [False, True])
def test_context_governance_and_flow_share_only_active_major_scope(facts, invalid, only_invalid):
    from app.core.affairs_security import build_affairs_context, student_directory_scope
    from app.models import Major, RoleAssignmentScope
    from app.modules.academic_affairs.services import academic_affairs_flow_service as flow
    from app.modules.academic_affairs.services import academic_affairs_program_governance_service as governance

    user = facts['major_user']
    with get_sessionmaker()() as db:
        original_scope = db.get(RoleAssignmentScope, facts['scope'])
        db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=original_scope.user_role_id,
            user_id=int(user['userId']), role_code=user['currentRoleCode'], scope_type='MAJOR',
            scope_id=facts['sibling'], status='ACTIVE', effective_at=datetime(2020, 1, 1)))
        invalid_major = db.get(Major, facts['sibling'])
        if invalid == 'disabled':
            invalid_major.status = 'DISABLED'
        else:
            invalid_major.is_deleted = True
        if only_invalid:
            original_scope.status = 'REVOKED'
        db.commit()
    expected = set() if only_invalid else {facts['major']}
    with get_sessionmaker()() as db:
        context = build_affairs_context(user, db)
        assert context.major_ids == expected
        assert context.scope_type == ('NONE' if only_invalid else 'CLASS')
        assert context.class_ids == set() and context.college_ids == set()
        assert governance._allowed_major_ids(db, context) == expected
        assert flow._major_scope(db, user, context) == expected
    assert student_directory_scope(user) == (set(), None)
    _denied(lambda: programs.get_program(facts['programs']['sibling'], user))
    _denied(lambda: programs.create_program(_program_body(facts['sibling']), user))
    if only_invalid:
        _denied(lambda: programs.get_program(facts['programs']['own'], user))
        _denied(lambda: programs.create_program(_program_body(facts['major']), user))
    else:
        assert programs.get_program(facts['programs']['own'], user)['majorId'] == str(facts['major'])


def test_named_student_scope_keeps_priority_while_empty_major_program_remains_manageable(facts):
    from app.core.affairs_security import build_affairs_context, student_directory_scope
    from app.models import RoleAssignmentScope, StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_flow_service as flow

    user = facts['major_user']
    with get_sessionmaker()() as db:
        named = StudentProfile(tenant_id=TID, student_no='T07-NAMED', real_name='隔离点名学生',
            class_id=facts['sibling_class'], college_id=facts['college'], major_id=facts['sibling'],
            current_stage='ON_CAMPUS', student_status='REGISTERED', status='ACTIVE')
        peer = StudentProfile(tenant_id=TID, student_no='T07-PEER', real_name='隔离同班学生',
            class_id=facts['sibling_class'], college_id=facts['college'], major_id=facts['sibling'],
            current_stage='ON_CAMPUS', student_status='REGISTERED', status='ACTIVE')
        db.add_all([named, peer]); db.flush()
        original_scope = db.get(RoleAssignmentScope, facts['scope'])
        db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=original_scope.user_role_id,
            user_id=int(user['userId']), role_code=user['currentRoleCode'], scope_type='STUDENT',
            scope_id=named.id, status='ACTIVE', effective_at=datetime(2020, 1, 1)))
        named_id, peer_id = named.id, peer.id
        db.commit()
    with get_sessionmaker()() as db:
        context = build_affairs_context(user, db)
        assert context.scope_type == 'STUDENT'
        assert context.major_ids == {facts['major']}
        assert context.student_ids == {named_id}
        assert context.class_ids == set() and context.college_ids == set()
        assert context.require_student(db, named_id).id == named_id
        _denied(lambda: context.require_student(db, peer_id))
    assert student_directory_scope(user) == (None, {named_id})
    assert programs.get_program(facts['programs']['own'], user)['majorId'] == str(facts['major'])
    edited = programs.update_program(facts['programs']['own'], user,
        SimpleNamespace(programName='保留点名边界的专业方案'))
    assert edited['programName'] == '保留点名边界的专业方案'
    created = programs.create_program(_program_body(facts['major']), user)
    assert programs.get_program(created['programId'], user)['majorId'] == str(facts['major'])
    _denied(lambda: programs.get_program(facts['programs']['sibling'], user))
    assert student_directory_scope(user) == (None, {named_id})
    projection = flow.flow(user)
    assert projection['viewer']['scopeType'] == 'STUDENT'
    assert projection['viewer']['majorIds'] == [str(facts['major'])]
    assert projection['viewer']['collegeIds'] == []
    assert projection['unitProgress'] == [] and projection['schoolGates'] == []
    assert projection['schoolStage'] is None
    program_stage = projection['stages'][2]
    assert program_stage['evidence']['majorIds'] == [str(facts['major'])]
    assert program_stage['evidence']['programCount'] == 2
    assert program_stage['responsibility']['assigneeUserIds'] == [user['userId']]
    _denied(lambda: flow.flow(user, college_id=facts['college']))
    with get_sessionmaker()() as db:
        db.get(RoleAssignmentScope, facts['scope']).status = 'REVOKED'
        db.commit()
    _denied(lambda: flow.flow(user))
    assert student_directory_scope(user) == (None, {named_id})
    with get_sessionmaker()() as db:
        context = build_affairs_context(user, db)
        assert context.major_ids == set()
        assert context.require_student(db, named_id).id == named_id
        _denied(lambda: context.require_student(db, peer_id))


@pytest.mark.parametrize('invalid', ['member_revoked', 'member_expired', 'member_deleted',
                                    'role_disabled', 'validity_expired', 'user_disabled'])
def test_major_scope_requires_live_role_membership_even_when_scope_is_active(facts, invalid):
    from app.core.affairs_security import build_affairs_context, student_directory_scope
    from app.models import Role, RoleAssignmentScope, User, UserRole
    from app.models.role_assignment import RoleAssignmentValidity

    user = facts['major_user']
    with get_sessionmaker()() as db:
        scope = db.get(RoleAssignmentScope, facts['scope'])
        link = db.get(UserRole, scope.user_role_id)
        if invalid == 'member_revoked':
            link.status = 'REVOKED'
        elif invalid == 'member_expired':
            link.status = 'EXPIRED'
        elif invalid == 'member_deleted':
            link.is_deleted = True
        elif invalid == 'role_disabled':
            db.get(Role, link.role_id).status = 'DISABLED'
        elif invalid == 'user_disabled':
            db.get(User, int(user['userId'])).status = 'DISABLED'
        else:
            db.add(RoleAssignmentValidity(tenant_id=TID, user_role_id=link.id,
                user_id=int(user['userId']), role_code=user['currentRoleCode'], status='ACTIVE',
                source_type='MANUAL', effective_at=datetime(2020, 1, 1),
                expires_at=datetime.utcnow() - timedelta(days=1), reason='已到期专业岗位授权'))
            # The sweep has not run: the reader must enforce the validity window itself.
            assert link.status == 'ACTIVE' and not link.is_deleted
        assert scope.status == 'ACTIVE' and not scope.is_deleted and scope.expires_at is None
        db.commit()
    with get_sessionmaker()() as db:
        context = build_affairs_context(user, db)
        assert context.major_ids == set()
        assert context.scope_type == 'NONE'
        assert context.class_ids == set() and context.college_ids == set()
    _denied(lambda: programs.get_program(facts['programs']['own'], user))
    _denied(lambda: programs.update_program(facts['programs']['own'], user,
        SimpleNamespace(programName='失效身份不能写入')))
    _denied(lambda: programs.create_program(_program_body(facts['major']), user))
    assert student_directory_scope(user) == (set(), None)


@pytest.mark.parametrize('condition,expected', [
    ('revoked_secretary', True), ('active_secretary', False), ('active_college_leader', False),
    ('legacy_without_history', False), ('school_expired', False), ('school_permission_revoked', False),
])
def test_school_transfer_obeys_formal_revocation_and_legacy_fallback(facts, condition, expected):
    from app.models import College, Permission, RolePermission, StaffAssignment

    user = facts['school_user']
    set_current_user(user)
    secretary = None
    if condition != 'legacy_without_history':
        secretary = appointments.create_assignment(user_id=int(user['userId']), org_type='COLLEGE',
            org_node_id=facts['college'], assignment_type='SECRETARY', tenant_id=TID,
            effective_at=datetime(2020, 1, 1), reason='隔离学院原任职')
        if condition != 'active_secretary':
            appointments.revoke_assignment(int(secretary['assignmentId']), reason='正式校级转岗',
                expected_version=int(secretary['version']), tenant_id=TID)
    school = appointments.create_assignment(user_id=int(user['userId']), org_type='SCHOOL',
        org_node_id=TID, assignment_type='ACADEMIC_REVIEWER', tenant_id=TID,
        effective_at=datetime(2020, 1, 1), reason='隔离校级接任')
    if condition == 'active_college_leader':
        appointments.create_assignment(user_id=int(user['userId']), org_type='COLLEGE',
            org_node_id=facts['college'], assignment_type='LEADER', tenant_id=TID,
            effective_at=datetime(2020, 1, 1), reason='仍有学院在岗职责')
    with get_sessionmaker()() as db:
        if condition == 'school_expired':
            db.get(StaffAssignment, int(school['assignmentId'])).expires_at = datetime.utcnow() - timedelta(days=1)
        elif condition == 'school_permission_revoked':
            grant = db.scalar(select(RolePermission).join(Permission, Permission.id == RolePermission.permission_id)
                .where(RolePermission.tenant_id == TID, RolePermission.role_id == facts['school_role'],
                       Permission.permission_code == 'academicAffairs.program.review'))
            grant.status = 'DISABLED'
        db.commit()
    with get_sessionmaker()() as db:
        assert db.get(College, facts['college']).secretary_id == int(user['userId'])
        if secretary is not None and condition != 'active_secretary':
            assert db.get(StaffAssignment, int(secretary['assignmentId'])).status == 'REVOKED'
        result = responsibility.resolve_school(db, permission_code='academicAffairs.program.review')
        assert result['resolved'] is expected
        assert result['assigneeUserIds'] == ([user['userId']] if expected else [])
        assert result['orgType'] == 'SCHOOL'
