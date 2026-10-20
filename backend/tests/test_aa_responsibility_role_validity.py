"""Responsibility uses live login membership validity, including multi-role actors."""
from datetime import timedelta

import pytest

from tests.test_aa_responsibility_role_state import PERMISSION, TID, owner  # shared isolated fixture


@pytest.mark.parametrize("state", ["active", "expired", "future", "revoked", "deleted", "wrong-user", "wrong-role"])
@pytest.mark.parametrize("cached", [False, True])
def test_role_term_matches_login_and_does_not_allocate_expired_reviewer(owner, state, cached):
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentValidity, User
    from app.services.auth_service_db import _role_contexts
    from app.services.role_assignment_service import _now
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as service

    now = _now()
    with get_sessionmaker()() as db:
        role, user = db.get(Role, owner["role"]), db.get(User, owner["user"])
        validity = RoleAssignmentValidity(tenant_id=TID, user_role_id=owner["link"],
            user_id=user.id, role_code=role.role_code, effective_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=1), status="ACTIVE")
        if state == "expired":
            validity.expires_at = now - timedelta(seconds=1)
        elif state == "future":
            validity.effective_at = now + timedelta(days=1)
        elif state == "revoked":
            validity.status = "REVOKED"
        elif state == "deleted":
            validity.is_deleted = True
        elif state == "wrong-user":
            validity.user_id = user.id + 100000
        elif state == "wrong-role":
            validity.role_code = "ANOTHER_ROLE"
        db.add(validity); db.commit()
        expected = state == "active"
        assert any(c["contextId"] == f"role:{role.id}" for c in _role_contexts(db, user)) is expected
        result = service.resolve_school(db, permission_code=PERMISSION, cache={} if cached else None)
        assert (str(user.id) in result["assigneeUserIds"]) is expected


@pytest.mark.parametrize("cached", [False, True])
def test_live_college_permission_cannot_revive_expired_school_context(owner, cached):
    from app.db.session import get_sessionmaker
    from app.models import (College, Role, RoleAssignmentScope, RoleAssignmentValidity,
                            RolePermission, User, UserRole)
    from app.services.role_assignment_service import _now
    from tests.support_grade_review_identity import _ensure_permission
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as service
    from app.modules.academic_affairs.services.academic_affairs_grade_task_assignee_guard import _runtime_permission_holder_ids

    now = _now()
    with get_sessionmaker()() as db:
        user, school_role = db.get(User, owner["user"]), db.get(Role, owner["role"])
        db.add(RoleAssignmentValidity(tenant_id=TID, user_role_id=owner["link"], user_id=user.id,
            role_code=school_role.role_code, effective_at=now - timedelta(days=2),
            expires_at=now - timedelta(days=1), status="ACTIVE"))
        college = College(tenant_id=TID, college_name="有效学院范围", status="ACTIVE")
        role = Role(tenant_id=TID, role_code=f"COLLEGE_SCOPE_{user.id}", role_name="有效学院办理人",
                    role_type="CUSTOM", status="ACTIVE")
        db.add_all([college, role]); db.flush()
        member = UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE")
        db.add(member); db.flush()
        db.add(RolePermission(tenant_id=TID, role_id=role.id,
            permission_id=_ensure_permission(db, PERMISSION).id, status="ACTIVE"))
        db.add(RoleAssignmentScope(tenant_id=TID, user_id=user.id, user_role_id=member.id,
            role_code=role.role_code, scope_type="COLLEGE", scope_id=college.id,
            effective_at=now - timedelta(days=1), status="ACTIVE"))
        db.commit()
        assert user.id in _runtime_permission_holder_ids(db, PERMISSION)
        result = service.resolve_school(db, permission_code=PERMISSION, cache={} if cached else None)
        assert str(user.id) not in result["assigneeUserIds"]


def test_domain_priority_ignores_expired_membership_even_with_another_live_grant(owner):
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentValidity, User, UserRole
    from app.services.role_assignment_service import _now
    from app.modules.academic_affairs.services.academic_affairs_grade_task_assignee_guard import _preferred_role_candidates

    now = _now()
    with get_sessionmaker()() as db:
        domain = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == "ACADEMIC_ADMIN").first()
        if domain is None:
            domain = Role(tenant_id=TID, role_code="ACADEMIC_ADMIN", role_name="教务管理员",
                          role_type="SYSTEM", status="ACTIVE")
            db.add(domain); db.flush()
        current = User(tenant_id=TID, login_name=f"current_domain_{owner['user']}", real_name="当前教务",
                       user_type="TEACHER", password_hash="unusable-test-only", status="ACTIVE")
        db.add(current); db.flush()
        expired_link = UserRole(tenant_id=TID, user_id=owner["user"], role_id=domain.id, status="ACTIVE")
        db.add_all([expired_link, UserRole(tenant_id=TID, user_id=current.id, role_id=domain.id, status="ACTIVE")])
        db.flush()
        db.add(RoleAssignmentValidity(tenant_id=TID, user_role_id=expired_link.id,
            user_id=owner["user"], role_code=domain.role_code, effective_at=now - timedelta(days=2),
            expires_at=now - timedelta(days=1), status="ACTIVE"))
        db.commit()
        assert _preferred_role_candidates(db, [owner["user"], current.id], "ACADEMIC_ADMIN") == [current.id]
