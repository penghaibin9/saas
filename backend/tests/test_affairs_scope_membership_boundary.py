"""Every explicit scope belongs to one live assignment, never another concurrent duty."""
from datetime import datetime, timedelta

import pytest

from test_affairs_security import TID, _base


@pytest.mark.parametrize("scope_type", ["SCHOOL", "COLLEGE", "MAJOR", "CLASS", "STUDENT"])
@pytest.mark.parametrize("assignment_state", ["valid", "revoked", "expired", "other_duty"])
def test_scope_requires_its_own_valid_assignment(db_mode, scope_type, assignment_state):
    from app.core.context import get_tenant, set_tenant
    from app.core.affairs_security import build_affairs_context
    from app.services.auth_service_db import _inject_org_scope_claims
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentScope, RoleAssignmentValidity, SchoolClass, User, UserRole

    ids = _base(db_mode)
    previous = get_tenant()
    set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            account = User(tenant_id=TID, login_name="scope_assignment_owner", real_name="范围测试人员",
                           user_type="TEACHER", password_hash="not-a-login-fixture", status="ACTIVE")
            roles = [Role(tenant_id=TID, role_code=code, role_name=code,
                          role_type="CUSTOM", status="ACTIVE") for code in ("SCOPE_DUTY_A", "SCOPE_DUTY_B")]
            db.add_all([account, *roles]); db.flush()
            links = [UserRole(tenant_id=TID, user_id=account.id, role_id=role.id, status="ACTIVE") for role in roles]
            db.add_all(links); db.flush()
            scope_id = {"SCHOOL": 0, "COLLEGE": ids["col1"], "CLASS": ids["cA"],
                        "STUDENT": ids["A"], "MAJOR": db.get(SchoolClass, ids["cA"]).major_id}[scope_type]
            db.add(RoleAssignmentScope(tenant_id=TID, user_id=account.id,
                user_role_id=links[1 if assignment_state == "other_duty" else 0].id,
                role_code=roles[0].role_code, scope_type=scope_type, scope_id=scope_id,
                effective_at=datetime.utcnow() - timedelta(days=1), status="ACTIVE"))
            # 同账号的另一专项有他院范围，当前职责不得借用。
            db.add(RoleAssignmentScope(tenant_id=TID, user_id=account.id, user_role_id=links[1].id,
                role_code=roles[1].role_code, scope_type="COLLEGE", scope_id=ids["col2"],
                effective_at=datetime.utcnow() - timedelta(days=1), status="ACTIVE"))
            if assignment_state == "revoked":
                links[0].status = "REVOKED"
            if assignment_state == "expired":
                db.add(RoleAssignmentValidity(tenant_id=TID, user_id=account.id, user_role_id=links[0].id,
                    role_code=roles[0].role_code, status="ACTIVE", effective_at=datetime(2020, 1, 1),
                    expires_at=datetime(2020, 1, 2)))
            db.flush()
            user = {"userId": str(account.id), "loginName": account.login_name,
                    "tenantId": str(TID), "currentRoleCode": roles[0].role_code, "userType": "TEACHER",
                    "activeContextId": f"role:{roles[0].id}"}
            ctx = build_affairs_context(user, db)
            claims = dict(user)
            _inject_org_scope_claims(db, account, claims)
            if assignment_state == "valid":
                assert ctx.is_scope_configured
                assert ctx.require_student(db, ids["A"]).id == ids["A"]
                assert ids["col2"] not in ctx.college_ids
                if scope_type == "COLLEGE":
                    assert claims["collegeIds"] == [str(ids["col1"])]
                    db.add(RoleAssignmentScope(tenant_id=TID, user_id=account.id, user_role_id=links[0].id,
                        role_code=roles[0].role_code, scope_type="COLLEGE", scope_id=ids["col2"],
                        effective_at=datetime.utcnow() - timedelta(days=1), status="ACTIVE"))
                    db.flush()
                    assert build_affairs_context(user, db).college_ids == {ids["col1"], ids["col2"]}
            else:
                assert ctx.scope_type == "NONE"
                assert not ctx.is_scope_configured
                assert not (ctx.college_ids or ctx.class_ids or ctx.student_ids or ctx.major_ids)
                assert not any(key in claims for key in ("collegeIds", "majorIds", "classIds", "studentIds"))
    finally:
        set_tenant(previous)
