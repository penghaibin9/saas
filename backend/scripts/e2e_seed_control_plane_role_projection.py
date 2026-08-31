"""Seed the twelve role-projection identities required by the IAM browser seal.

Safety is inherited from ``e2e_seed_playwright_tenants.assert_safe_target``:
only a local database whose name contains ``e2e`` or ``test`` is accepted.
The script creates identities and role/scope bindings only; all permissions for
SYSTEM roles continue to come from published RoleTemplate authority.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import select

from e2e_seed_playwright_tenants import assert_safe_target
from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import (
    CustomRoleSource,
    Permission,
    Role,
    RoleAssignmentScope,
    RolePermission,
    Tenant,
    User,
    UserRole,
)

SCHOOL_TENANT_ID = 1000000000000000003
PLATFORM_TENANT_ID = 1000000000000000000
SCHOOL_LOGIN = "admin"
PASSWORD = "E2eRole@2026"
CUSTOM_ROLE = "E2E_CUSTOM_MENU"
CUSTOM_PERMISSION = "internship.recruitment.view"

SCHOOL_ROLES = {
    "SCHOOL_ADMIN": ("学校管理员", "SCHOOL", 0),
    "SYS_ADMIN": ("系统管理员", "SCHOOL", 0),
    "ACADEMIC_ADMIN": ("教务管理员", "SCHOOL", 0),
    "COLLEGE_ADMIN": ("学院管理员", "COLLEGE", 990001),
    "ACADEMIC_TEACHER": ("任课教师", "SCHOOL", 0),
    "STUDENT_AFFAIRS": ("学工管理员", "SCHOOL", 0),
    "COUNSELOR": ("辅导员", "COLLEGE", 990001),
    "INTERN_MENTOR": ("实习指导教师", "STUDENT", 990101),
    "GRADUATION_ADMIN": ("毕业设计管理员", "SCHOOL", 0),
    CUSTOM_ROLE: ("E2E 自定义菜单角色", "COLLEGE", 990001),
}

PLATFORM_ROLES = {
    "PLATFORM_COMMERCIAL": ("e2e_platform_commercial", "平台商务"),
    "PLATFORM_OPERATIONS": ("e2e_platform_operations", "平台运维"),
    "PLATFORM_SECURITY_AUDITOR": ("e2e_platform_security", "平台安全审计"),
}


def _role(db, tenant_id: int, code: str, name: str, role_type: str) -> Role:
    item = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id,
        Role.role_code == code,
    )).first()
    if item is None:
        item = Role(
            tenant_id=tenant_id,
            role_code=code,
            role_name=name,
            role_type=role_type,
            status="ACTIVE",
        )
        db.add(item)
        db.flush()
    else:
        item.role_name = name
        item.role_type = role_type
        item.status = "ACTIVE"
        item.is_deleted = False
    return item


def _link(db, tenant_id: int, user_id: int, role: Role) -> UserRole:
    item = db.scalars(select(UserRole).where(
        UserRole.tenant_id == tenant_id,
        UserRole.user_id == user_id,
        UserRole.role_id == role.id,
    )).first()
    if item is None:
        item = UserRole(
            tenant_id=tenant_id,
            user_id=user_id,
            role_id=role.id,
            status="ACTIVE",
        )
        db.add(item)
        db.flush()
    else:
        item.status = "ACTIVE"
        item.is_deleted = False
    return item


def _scope(db, tenant_id: int, user_id: int, role: Role, link: UserRole,
           scope_type: str, scope_id: int) -> None:
    item = db.scalars(select(RoleAssignmentScope).where(
        RoleAssignmentScope.tenant_id == tenant_id,
        RoleAssignmentScope.user_role_id == link.id,
        RoleAssignmentScope.scope_type == scope_type,
        RoleAssignmentScope.scope_id == scope_id,
    )).first()
    if item is None:
        db.add(RoleAssignmentScope(
            tenant_id=tenant_id,
            user_role_id=int(link.id),
            user_id=user_id,
            role_code=role.role_code,
            scope_type=scope_type,
            scope_id=scope_id,
            scope_name_snapshot=f"E2E {scope_type} {scope_id}",
            source_type="E2E_ROLE_PROJECTION",
            status="ACTIVE",
            reason="W12 isolated browser role projection",
        ))
    else:
        item.user_id = user_id
        item.role_code = role.role_code
        item.status = "ACTIVE"
        item.is_deleted = False


def _custom_permission(db, role: Role) -> None:
    permission = db.scalars(select(Permission).where(
        Permission.permission_code == CUSTOM_PERMISSION,
    )).first()
    if permission is None:
        raise RuntimeError(f"Permission Catalog was not reconciled: {CUSTOM_PERMISSION}")
    link = db.scalars(select(RolePermission).where(
        RolePermission.tenant_id == SCHOOL_TENANT_ID,
        RolePermission.role_id == role.id,
        RolePermission.permission_id == permission.id,
    )).first()
    if link is None:
        db.add(RolePermission(
            tenant_id=SCHOOL_TENANT_ID,
            role_id=int(role.id),
            permission_id=int(permission.id),
            status="ACTIVE",
        ))
    else:
        link.status = "ACTIVE"
        link.is_deleted = False

    source = db.scalars(select(CustomRoleSource).where(
        CustomRoleSource.tenant_id == SCHOOL_TENANT_ID,
        CustomRoleSource.role_code == CUSTOM_ROLE,
    )).first()
    payload = {"items": [CUSTOM_PERMISSION]}
    if source is None:
        db.add(CustomRoleSource(
            tenant_id=SCHOOL_TENANT_ID,
            role_id=int(role.id),
            role_code=CUSTOM_ROLE,
            source_template_code="ACADEMIC_TEACHER",
            source_template_version=1,
            permission_codes_json=payload,
            drift_json={"pinned": True, "automaticUpgrade": False},
            status="ACTIVE",
        ))
    else:
        source.role_id = int(role.id)
        source.permission_codes_json = payload
        source.drift_json = {"pinned": True, "automaticUpgrade": False}
        source.status = "ACTIVE"
        source.is_deleted = False


def _platform_user(db, code: str, login: str, name: str) -> User:
    item = db.scalars(select(User).where(
        User.tenant_id == PLATFORM_TENANT_ID,
        User.login_name == login,
    )).first()
    if item is None:
        item = User(
            tenant_id=PLATFORM_TENANT_ID,
            login_name=login,
            real_name=name,
            password_hash=hash_password(PASSWORD),
            user_type="PLATFORM_OP",
            status="ACTIVE",
            must_change_password=False,
        )
        db.add(item)
        db.flush()
    else:
        item.password_hash = hash_password(PASSWORD)
        item.user_type = "PLATFORM_OP"
        item.status = "ACTIVE"
        item.must_change_password = False
        item.is_deleted = False
    role = _role(db, PLATFORM_TENANT_ID, code, name, "SYSTEM")
    _link(db, PLATFORM_TENANT_ID, int(item.id), role)
    return item


def main() -> int:
    assert_safe_target()
    db = get_sessionmaker()()
    try:
        school_user = db.scalars(select(User).where(
            User.tenant_id == SCHOOL_TENANT_ID,
            User.login_name == SCHOOL_LOGIN,
            User.is_deleted.is_(False),
        )).first()
        platform_tenant = db.get(Tenant, PLATFORM_TENANT_ID)
        if school_user is None:
            raise RuntimeError("run e2e_seed_playwright_tenants.py first")
        if platform_tenant is None:
            platform_tenant = Tenant(
                id=PLATFORM_TENANT_ID,
                tenant_code="platform",
                school_name="平台运营中心",
                short_name="平台",
                status="ACTIVE",
            )
            db.add(platform_tenant)
            db.flush()

        school_contexts = []
        for code, (name, scope_type, scope_id) in SCHOOL_ROLES.items():
            role = _role(db, SCHOOL_TENANT_ID, code, name, "CUSTOM" if code == CUSTOM_ROLE else "SYSTEM")
            link = _link(db, SCHOOL_TENANT_ID, int(school_user.id), role)
            _scope(db, SCHOOL_TENANT_ID, int(school_user.id), role, link, scope_type, scope_id)
            if code == CUSTOM_ROLE:
                _custom_permission(db, role)
            school_contexts.append({"roleCode": code, "roleId": str(role.id), "scopeType": scope_type})

        platform_users = []
        for code, (login, name) in PLATFORM_ROLES.items():
            user = _platform_user(db, code, login, name)
            platform_users.append({"roleCode": code, "login": login, "userId": str(user.id)})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    fixture = {
        "headSha": str(os.getenv("E2E_EXPECTED_SHA") or os.getenv("GITHUB_SHA") or ""),
        "schoolTenantCode": "demo-school",
        "schoolLogin": SCHOOL_LOGIN,
        "schoolContexts": school_contexts,
        "platformUsers": platform_users,
        "customPermission": CUSTOM_PERMISSION,
    }
    target = Path(__file__).resolve().parents[2] / "e2e" / "runtime-fixtures" / "control-plane-role-projection.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(fixture, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(fixture, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
