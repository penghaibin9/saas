"""生产审计 Issue 2：critical audit 必须能与业务事实共享同一事务。"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.context import set_tenant
from app.services import audit_log
from app.services.audit_log import AuditPersistenceError

TENANT_ID = 1000000000000000001
ACTION = "USER_ROLE_ASSIGN"


def _session():
    from app.db.session import get_sessionmaker
    return get_sessionmaker()()


def _ensure_tenant() -> None:
    from app.models import Tenant
    with _session() as db:
        if db.get(Tenant, TENANT_ID) is None:
            db.add(Tenant(id=TENANT_ID, tenant_code="audit-atomicity",
                          school_name="审计原子性测试学校", status="ACTIVE"))
            db.commit()
    set_tenant({"tenantId": TENANT_ID})


def _count(resource: str) -> int:
    from app.models import SecurityAuditLog
    with _session() as db:
        return int(db.scalar(select(func.count(SecurityAuditLog.id)).where(
            SecurityAuditLog.tenant_id == TENANT_ID,
            SecurityAuditLog.action == ACTION,
            SecurityAuditLog.resource == resource,
        )) or 0)


def test_record_critical_in_session_rollback_removes_audit_fact(db_mode):
    _ensure_tenant()
    resource = f"atomic-rollback-{uuid.uuid4().hex}"
    with _session() as db:
        audit_log.record_critical_in_session(
            db, ACTION, resource, detail={"reason": "故障注入回滚验证"}, tenant_id=TENANT_ID
        )
        db.flush()
        db.rollback()
    assert _count(resource) == 0


def test_record_critical_in_session_commit_persists_audit_fact(db_mode):
    _ensure_tenant()
    resource = f"atomic-commit-{uuid.uuid4().hex}"
    with _session() as db:
        audit_log.record_critical_in_session(
            db, ACTION, resource, detail={"reason": "同事务提交验证"}, tenant_id=TENANT_ID
        )
        db.commit()
    assert _count(resource) == 1


def test_record_critical_in_session_propagates_insert_failure(db_mode, monkeypatch):
    from app.services import db_service
    _ensure_tenant()

    def _boom(*args, **kwargs):
        raise RuntimeError("forced audit insert failure")

    monkeypatch.setattr(db_service, "audit_insert_in_session", _boom)
    with _session() as db, pytest.raises(AuditPersistenceError):
        audit_log.record_critical_in_session(
            db, ACTION, f"atomic-fail-{uuid.uuid4().hex}",
            detail={"reason": "故障注入"}, tenant_id=TENANT_ID
        )


def test_record_critical_in_session_rejects_noncritical_action(db_mode):
    _ensure_tenant()
    with _session() as db, pytest.raises(ValueError):
        audit_log.record_critical_in_session(
            db, "LOGIN_SUCCESS", "not-critical", detail={}, tenant_id=TENANT_ID
        )


def _atomic_actor() -> dict:
    return {
        "userId": "db-910001",
        "tenantId": str(TENANT_ID),
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "TEACHER",
        "realName": "原子审计管理员",
    }


def _atomic_user(login_prefix: str = "audit_atomic_user") -> int:
    from app.core.security import hash_password
    from app.models import User
    _ensure_tenant()
    login = f"{login_prefix}_{uuid.uuid4().hex[:10]}"
    with _session() as db:
        row = User(
            tenant_id=TENANT_ID, login_name=login, real_name="原子审计账号",
            password_hash=hash_password("Init123456"), user_type="TEACHER",
            status="ACTIVE", must_change_password=False,
        )
        db.add(row)
        db.commit()
        return int(row.id)


def _atomic_role(code: str, *, role_type: str = "SYSTEM") -> int:
    from app.models import Role
    _ensure_tenant()
    with _session() as db:
        row = db.scalars(select(Role).where(
            Role.tenant_id == TENANT_ID, Role.role_code == code,
            Role.is_deleted.is_(False),
        )).first()
        if row is None:
            row = Role(
                tenant_id=TENANT_ID, role_code=code, role_name=code,
                role_type=role_type, status="ACTIVE",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        return int(row.id)


def _force_audit_failure(monkeypatch):
    from app.services import db_service

    def _boom(*args, **kwargs):
        raise RuntimeError("forced critical audit insert failure")

    monkeypatch.setattr(db_service, "audit_insert_in_session", _boom)


def test_user_role_assignment_rolls_back_when_critical_audit_insert_fails(db_mode, monkeypatch):
    from app.api.v1.system import assign_system_user_roles
    from app.models import Role, User, UserRole

    _atomic_role("COUNSELOR")
    user_id = _atomic_user("audit_role_assign")
    with _session() as db:
        before_version = int(db.get(User, user_id).version or 0)
    _force_audit_failure(monkeypatch)

    with pytest.raises(AuditPersistenceError):
        assign_system_user_roles(
            user_id, {"roleCodes": ["COUNSELOR"]}, user=_atomic_actor()
        )

    with _session() as db:
        account = db.get(User, user_id)
        link = db.scalars(select(UserRole).join(Role, Role.id == UserRole.role_id).where(
            UserRole.tenant_id == TENANT_ID,
            UserRole.user_id == user_id,
            Role.role_code == "COUNSELOR",
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
        )).first()
        assert int(account.version or 0) == before_version
        assert link is None


def test_role_permission_save_rolls_back_when_critical_audit_insert_fails(db_mode, monkeypatch):
    from app.api.v1.system import save_system_role_permissions
    from app.models import Permission, Role, RolePermission

    role_id = _atomic_role(f"CUSTOM_AUDIT_{uuid.uuid4().hex[:8].upper()}", role_type="CUSTOM")
    code = "systemAdmin.audit.sensitive.view"
    with _session() as db:
        before_version = int(db.get(Role, role_id).version or 0)
    _force_audit_failure(monkeypatch)

    with pytest.raises(AuditPersistenceError):
        save_system_role_permissions(
            role_id,
            {"permissionCodes": [code], "visiblePermissionCodes": [code]},
            user=_atomic_actor(),
        )

    with _session() as db:
        role = db.get(Role, role_id)
        link = db.scalars(select(RolePermission).join(
            Permission, Permission.id == RolePermission.permission_id
        ).where(
            RolePermission.tenant_id == TENANT_ID,
            RolePermission.role_id == role_id,
            Permission.permission_code == code,
            RolePermission.status == "ACTIVE",
            RolePermission.is_deleted.is_(False),
        )).first()
        assert int(role.version or 0) == before_version
        assert link is None


def test_admin_password_reset_rolls_back_when_critical_audit_insert_fails(db_mode, monkeypatch):
    from app.api.v1.system import reset_system_user_password
    from app.models import User

    user_id = _atomic_user("audit_reset_password")
    with _session() as db:
        account = db.get(User, user_id)
        before_hash = account.password_hash
        before_version = int(account.version or 0)
        before_force = bool(account.must_change_password)
    _force_audit_failure(monkeypatch)

    with pytest.raises(AuditPersistenceError):
        reset_system_user_password(
            user_id, {"expectedVersion": before_version}, user=_atomic_actor()
        )

    with _session() as db:
        account = db.get(User, user_id)
        assert account.password_hash == before_hash
        assert int(account.version or 0) == before_version
        assert bool(account.must_change_password) == before_force


def test_tenant_transition_rolls_back_when_critical_audit_insert_fails(db_mode, monkeypatch):
    from app.services.tenant_effective_state_service import apply_transition, get_effective_state

    _ensure_tenant()
    before = get_effective_state(TENANT_ID, strict=True)
    _force_audit_failure(monkeypatch)

    with pytest.raises(AuditPersistenceError):
        apply_transition(
            TENANT_ID,
            "disable",
            reason="故障注入验证租户状态回滚",
            expected_version=int(before["version"]),
            payload={},
            audit_action="PLATFORM_TENANT_DISABLE",
        )

    after = get_effective_state(TENANT_ID, strict=True)
    assert after["effectiveStatus"] == before["effectiveStatus"]
    assert after["rowStatus"] == before["rowStatus"]
    assert int(after["version"]) == int(before["version"])
