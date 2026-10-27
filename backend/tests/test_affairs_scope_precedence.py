from datetime import datetime, timedelta

import pytest

from test_affairs_security import TID, _base


@pytest.mark.parametrize("state", ["ACTIVE", "REVOKED", "EXPIRED", "DELETED"])
def test_canonical_scope_never_falls_back_to_legacy_grant(db_mode, state):
    from app.core.affairs_security import build_affairs_context
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentScope, TeacherStudentScope, User, UserRole
    from app.services.affairs_mental_service import psy_scope_ids
    from app.services.auth_service_db import _inject_org_scope_claims
    from app.core.exceptions import AppException
    from app.services.affairs_risk_service import _scope_or_403
    from types import SimpleNamespace

    ids = _base(db_mode)
    previous = get_tenant()
    set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            account = User(tenant_id=TID, login_name="scope_precedence", real_name="范围测试",
                           user_type="TEACHER", password_hash="unused-test-hash", status="ACTIVE")
            role = Role(tenant_id=TID, role_code="PSYCHOLOGY_TEACHER", role_name="心理职责",
                        role_type="SYSTEM", status="ACTIVE")
            db.add_all([account, role]); db.flush()
            member = UserRole(tenant_id=TID, user_id=account.id, role_id=role.id, status="ACTIVE")
            db.add(member); db.flush()
            db.add(TeacherStudentScope(tenant_id=TID, teacher_key=account.login_name,
                role_code=role.role_code, scope_type="PSY_STUDENT", ref_value="C001", status="ACTIVE"))
            db.flush()
            user = {"userId": str(account.id), "loginName": account.login_name,
                    "tenantId": str(TID), "currentRoleCode": role.role_code}
            assert psy_scope_ids(db, user) == {ids["C"]}
            db.add(RoleAssignmentScope(tenant_id=TID, user_id=account.id, user_role_id=member.id,
                role_code=role.role_code, scope_type="STUDENT", scope_id=ids["A"],
                status="REVOKED" if state == "REVOKED" else "ACTIVE", is_deleted=state == "DELETED",
                effective_at=datetime.utcnow() - timedelta(days=2),
                expires_at=datetime.utcnow() - timedelta(days=1) if state == "EXPIRED" else None))
            db.flush()
            expected = {ids["A"]} if state == "ACTIVE" else set()
            assert psy_scope_ids(db, user) == expected
            ctx = build_affairs_context(user, db)
            assert ctx.student_ids == expected
            claims = dict(user)
            _inject_org_scope_claims(db, account, claims)
            assert set(claims.get("studentIds", [])) == {str(value) for value in expected}
            owned = SimpleNamespace(owner_id=account.id, source="MENTAL")
            with pytest.raises(AppException):
                _scope_or_403(db, ids["C"], user, owned)
            if state == "ACTIVE":
                _scope_or_403(db, ids["A"], user, owned)
            else:
                with pytest.raises(AppException):
                    _scope_or_403(db, ids["A"], user, owned)
    finally:
        set_tenant(previous)
