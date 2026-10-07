"""Current responsibility must match login role states without reviving disabled links."""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.core.context import get_tenant, set_tenant

TID = 1000000000000000001
PERMISSION = "academicAffairs.schedule.edit"


@pytest.fixture
def owner(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentScope, RolePermission, StaffAssignment, User, UserRole
    from tests.support_grade_review_identity import _ensure_permission

    previous = get_tenant()
    set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            suffix = uuid4().hex[:12]
            person = User(tenant_id=TID, login_name="state_" + suffix, real_name="责任状态回归",
                          user_type="TEACHER", password_hash="unusable-test-only", status="ACTIVE")
            role = Role(tenant_id=TID, role_code="STATE_" + suffix.upper(),
                        role_name="责任状态回归", role_type="CUSTOM", status="ENABLED")
            db.add_all([person, role])
            db.flush()
            link = UserRole(tenant_id=TID, user_id=person.id, role_id=role.id, status="ACTIVE")
            db.add(link)
            db.flush()
            permission = _ensure_permission(db, PERMISSION)
            db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status="ACTIVE"))
            db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=link.id, user_id=person.id,
                                      role_code=role.role_code, scope_type="SCHOOL", scope_id=TID,
                                      effective_at=datetime(2020, 1, 1), status="ACTIVE"))
            appointment = StaffAssignment(tenant_id=TID, user_id=person.id, org_type="SCHOOL",
                                          org_node_id=TID, assignment_type="ACADEMIC_REVIEWER",
                                          effective_at=datetime(2020, 1, 1), status="ACTIVE")
            db.add(appointment)
            db.flush()
            ids = dict(user=person.id, role=role.id, link=link.id, appointment=appointment.id)
            db.commit()
        yield ids
    finally:
        set_tenant(previous)


@pytest.mark.parametrize("state, expected", [("ACTIVE", True), ("ENABLED", True), ("DISABLED", False)])
@pytest.mark.parametrize("cached", [False, True])
def test_school_responsibility_uses_same_enabled_role_states_as_login(owner, state, expected, cached):
    from app.db.session import get_sessionmaker
    from app.models import Role, User
    from app.services.auth_service_db import _role_contexts
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as service

    with get_sessionmaker()() as db:
        role = db.get(Role, owner["role"])
        role.status = state
        db.commit()
        person = db.get(User, owner["user"])
        login_contexts = _role_contexts(db, person)
        assert any(row["contextId"] == f"role:{role.id}" for row in login_contexts) is expected
        result = service.resolve_school(db, permission_code=PERMISSION, cache={} if cached else None)
        assert (str(person.id) in result["assigneeUserIds"]) is expected


@pytest.mark.parametrize("revocation", ["membership", "user", "appointment", "expired", "future"])
def test_enabled_role_does_not_revive_inactive_user_membership_or_appointment(owner, revocation):
    from app.db.session import get_sessionmaker
    from app.models import StaffAssignment, User, UserRole
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as service

    with get_sessionmaker()() as db:
        assert str(owner["user"]) in service.resolve_school(db, permission_code=PERMISSION)["assigneeUserIds"]
        if revocation == "membership":
            db.get(UserRole, owner["link"]).status = "DISABLED"
        elif revocation == "user":
            db.get(User, owner["user"]).status = "DISABLED"
        else:
            row = db.get(StaffAssignment, owner["appointment"])
            if revocation == "appointment":
                row.status = "REVOKED"
            elif revocation == "expired":
                row.expires_at = datetime.utcnow() - timedelta(days=1)
            else:
                row.effective_at = datetime.utcnow() + timedelta(days=1)
        db.commit()
        # A new request/command must see revocation; no cross-request cache reuse.
        for cache in (None, {}):
            result = service.resolve_school(db, permission_code=PERMISSION, cache=cache)
            assert str(owner["user"]) not in result["assigneeUserIds"]
