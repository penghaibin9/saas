from datetime import datetime, timedelta

import pytest

from test_affairs_security import TID, _base


@pytest.fixture(autouse=True)
def tenant_context(db_mode):
    from app.core.context import get_tenant, set_tenant
    previous = get_tenant()
    set_tenant(TID)
    yield
    set_tenant(previous)


@pytest.mark.parametrize("binding", ["explicit", "empty_role", "other_role", "name_only"])
def test_legacy_scope_requires_current_duty_and_stable_key(db_mode, binding):
    from app.core.affairs_security import build_affairs_context
    from app.db.session import get_sessionmaker
    from app.models import College, TeacherStudentScope, User
    from app.services.auth_service_db import _inject_org_scope_claims
    ids = _base(db_mode)
    with get_sessionmaker()() as db:
        account = User(tenant_id=TID, login_name="legacy_owner", real_name="同名老师",
                       user_type="TEACHER", password_hash="unused-test-hash", status="ACTIVE")
        db.add(account); db.flush()
        db.add(TeacherStudentScope(tenant_id=TID,
            teacher_key="another_account" if binding == "name_only" else account.login_name,
            teacher_name=account.login_name if binding == "name_only" else account.real_name,
            role_code="" if binding == "empty_role" else "FUNDING_TEACHER" if binding == "other_role" else "COLLEGE_ADMIN",
            scope_type="COLLEGE", ref_value=db.get(College, ids["col1"]).college_name, status="ACTIVE"))
        db.flush()
        user = {"userId": str(account.id), "loginName": account.login_name,
                "currentRoleCode": "COLLEGE_ADMIN", "tenantId": str(TID)}
        ctx = build_affairs_context(user, db)
        claims = dict(user)
        _inject_org_scope_claims(db, account, claims)
        if binding == "explicit":
            assert ctx.college_ids == {ids["col1"]}
            assert claims["collegeIds"] == [str(ids["col1"])]
        else:
            assert ctx.scope_type == "NONE"
            assert "collegeIds" not in claims


@pytest.mark.parametrize("state", ["active", "expired", "revoked"])
@pytest.mark.parametrize("modern", [False, True])
def test_formal_counselor_term_wins_over_old_class_and_scope_fields(db_mode, state, modern):
    from app.core.affairs_security import build_affairs_context
    from app.db.session import get_sessionmaker
    from app.models import AffairsCounselorAssignment, Role, RoleAssignmentScope, SchoolClass, TeacherStudentScope, User, UserRole
    from app.services.affairs_assignee_service import resolve_assignee_ids
    ids = _base(db_mode)
    with get_sessionmaker()() as db:
        account = User(tenant_id=TID, login_name="term_owner", real_name="任期老师",
                       user_type="TEACHER", password_hash="unused-test-hash", status="ACTIVE")
        db.add(account); db.flush()
        role = Role(tenant_id=TID, role_code="COUNSELOR", role_name="辅导员", role_type="SYSTEM", status="ACTIVE")
        db.add(role); db.flush()
        member = UserRole(tenant_id=TID, role_id=role.id, user_id=account.id, status="ACTIVE")
        db.add(member); db.flush()
        school_class = db.get(SchoolClass, ids["cA"])
        school_class.counselor_id = account.id
        db.add(AffairsCounselorAssignment(tenant_id=TID, class_id=school_class.id, user_id=account.id,
            duty_type="PRIMARY", status="REVOKED" if state == "revoked" else "ACTIVE",
            effective_from=datetime.utcnow() - timedelta(days=2),
            effective_to=datetime.utcnow() - timedelta(days=1) if state == "expired" else None))
        db.add(TeacherStudentScope(tenant_id=TID, teacher_key=account.login_name, role_code="COUNSELOR",
            scope_type="CLASS", ref_value=school_class.class_name, status="ACTIVE"))
        if modern:
            db.add(RoleAssignmentScope(tenant_id=TID, user_id=account.id, user_role_id=member.id,
                role_code="COUNSELOR", scope_type="CLASS", scope_id=school_class.id, status="ACTIVE",
                effective_at=datetime.utcnow() - timedelta(days=2)))
        db.flush()
        user = {"userId": str(account.id), "loginName": account.login_name, "currentRoleCode": "COUNSELOR"}
        ctx = build_affairs_context(user, db)
        owners = resolve_assignee_ids(db, "COUNSELOR_REVIEW", student_id=ids["A"])
        if state == "active":
            assert ctx.class_ids == {ids["cA"]}
            assert owners == [account.id]
        else:
            assert ctx.scope_type == "NONE"
            assert owners == []
