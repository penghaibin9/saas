"""生产审计 Issue 1：永久角色授予只能使用 actor 的基础权限。"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.core.security import hash_password
from app.services import role_assignment_service as ras

TENANT_ID = 1000000000000000001


@pytest.fixture(autouse=True)
def _bootstrap_school_iam_authority(db_mode):
    """Each migrated-schema reset replays the same production Control Plane Authority."""
    from app.services.school_iam_authority_service import converge_school_iam_authority

    result = converge_school_iam_authority(
        source="PYTEST_ROLE_ASSIGNMENT_PRIVILEGE_BOUNDARY",
        source_commit_sha="pytest-role-assignment-boundary",
        actor_user_id=None,
    )
    assert result["converged"] is True
    assert result["shadow"]["zeroUnexplainedDrift"] is True
    assert result["catalogReconciliation"]["missingAfterReconcile"] == 0


def _session():
    from app.db.session import get_sessionmaker
    return get_sessionmaker()()


def _ensure_tenant(tenant_id: int = TENANT_ID) -> None:
    from app.models import Tenant
    with _session() as db:
        if db.get(Tenant, tenant_id) is None:
            db.add(Tenant(id=tenant_id, tenant_code=f"rbac-{tenant_id}", school_name="授权边界测试学校", status="ACTIVE"))
            db.commit()


def _role(code: str, *, role_type: str = "SYSTEM", tenant_id: int = TENANT_ID):
    from app.models import Role
    _ensure_tenant(tenant_id)
    with _session() as db:
        row = db.scalars(select(Role).where(Role.tenant_id == tenant_id, Role.role_code == code)).first()
        if row is None:
            row = Role(tenant_id=tenant_id, role_code=code, role_name=code, role_type=role_type, status="ACTIVE")
            db.add(row)
            db.commit()
            db.refresh(row)
        return int(row.id)


def _user(*, tenant_id: int = TENANT_ID) -> int:
    from app.models import User
    _ensure_tenant(tenant_id)
    login = f"rbac_{uuid.uuid4().hex[:12]}"
    with _session() as db:
        row = User(tenant_id=tenant_id, login_name=login, real_name="授权边界用户",
                   password_hash=hash_password("Init123456"), user_type="TEACHER", status="ACTIVE")
        db.add(row)
        db.commit()
        return int(row.id)


def _actor(role_code: str = "ACADEMIC_TEACHER") -> dict:
    return {"userId": "db-900001", "tenantId": str(TENANT_ID), "currentRoleCode": role_code, "userType": "TEACHER"}


def _temporary(monkeypatch, patterns):
    from app.services import system_governance_service as gov
    monkeypatch.setattr(gov, "active_delegation_permission_patterns", lambda user: list(patterns))


def _assert_no_active_role(user_id: int, role_code: str) -> None:
    from app.models import Role, UserRole
    with _session() as db:
        row = db.scalars(select(UserRole).join(Role, Role.id == UserRole.role_id).where(
            UserRole.tenant_id == TENANT_ID, UserRole.user_id == user_id,
            Role.role_code == role_code, UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False))).first()
        assert row is None


def test_new_role_assignment_rejects_role_above_actor_base_permissions(db_mode, monkeypatch):
    _role("SCHOOL_ADMIN")
    target = _user()
    _temporary(monkeypatch, ["*"])
    with pytest.raises(AppException) as caught:
        ras.grant_assignment(target, "SCHOOL_ADMIN", reason="安全边界测试授权", tenant_id=TENANT_ID, user=_actor())
    assert caught.value.code == "NO_PERMISSION"
    _assert_no_active_role(target, "SCHOOL_ADMIN")


def test_legacy_assign_roles_rejects_temporary_delegation_redelegation(db_mode, monkeypatch):
    from app.api.v1.system import assign_system_user_roles
    _role("SCHOOL_ADMIN")
    target = _user()
    set_tenant({"tenantId": TENANT_ID})
    _temporary(monkeypatch, ["*"])
    with pytest.raises(AppException) as caught:
        assign_system_user_roles(target, {"roleCodes": ["SCHOOL_ADMIN"]}, user=_actor())
    assert caught.value.code == "NO_PERMISSION"
    _assert_no_active_role(target, "SCHOOL_ADMIN")


def test_role_copy_cannot_persist_temporary_delegated_permission(db_mode, monkeypatch):
    from app.api.v1.system import copy_system_role
    role_id = _role("SECURITY_AUDITOR")
    set_tenant({"tenantId": TENANT_ID})
    _temporary(monkeypatch, ["*"])
    with pytest.raises(AppException) as caught:
        copy_system_role(role_id, user=_actor())
    assert caught.value.code == "NO_PERMISSION"


def test_role_permission_save_cannot_persist_temporary_delegated_permission(db_mode, monkeypatch):
    from app.api.v1.system import save_system_role_permissions
    role_id = _role(f"CUSTOM_{uuid.uuid4().hex[:8].upper()}", role_type="CUSTOM")
    code = "systemAdmin.audit.sensitive.view"
    set_tenant({"tenantId": TENANT_ID})
    _temporary(monkeypatch, [code])
    with pytest.raises(AppException) as caught:
        save_system_role_permissions(role_id, {"permissionCodes": [code], "visiblePermissionCodes": [code]}, user=_actor())
    assert caught.value.code == "NO_PERMISSION"


def test_school_role_governance_rejects_platform_role(db_mode, monkeypatch):
    _role("PLATFORM_OWNER")
    target = _user()
    _temporary(monkeypatch, ["*"])
    with pytest.raises(AppException) as caught:
        ras.grant_assignment(target, "PLATFORM_OWNER", reason="安全边界测试授权", tenant_id=TENANT_ID,
                             user=_actor("SCHOOL_ADMIN"))
    assert caught.value.code == "NO_PERMISSION"
    _assert_no_active_role(target, "PLATFORM_OWNER")


def test_base_wildcard_can_delegate_school_role(db_mode):
    _role("SECURITY_AUDITOR")
    target = _user()
    out = ras.grant_assignment(target, "SECURITY_AUDITOR", reason="学校管理员正常授权", tenant_id=TENANT_ID,
                               user=_actor("SCHOOL_ADMIN"))
    assert out["userId"] == str(target)
    assert out["roleCode"] == "SECURITY_AUDITOR"


def test_cross_tenant_role_assignment_fails_closed(db_mode):
    other_tenant = TENANT_ID + 91
    _role("SECURITY_AUDITOR")
    target = _user(tenant_id=other_tenant)
    with pytest.raises(AppException) as caught:
        ras.grant_assignment(target, "SECURITY_AUDITOR", reason="跨租户必须拒绝授权", tenant_id=TENANT_ID,
                             user=_actor("SCHOOL_ADMIN"))
    assert caught.value.code == "DATA_NOT_FOUND"