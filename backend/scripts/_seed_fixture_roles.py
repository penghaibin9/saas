"""Explicit roles for local/CI fixture accounts, never a runtime auth fallback.

Callers choose the account and role. No username lookup, automatic production
migration, role wildcard or reactivation of withdrawn assignments is permitted.
"""
from __future__ import annotations

from sqlalchemy import select

_ROLE_TYPES = {
    "SCHOOL_ADMIN": ("学校管理员", frozenset({"ADMIN", "SCHOOL_ADMIN"})),
    "COUNSELOR": ("辅导员", frozenset({"TEACHER"})),
    "STUDENT": ("学生", frozenset({"STUDENT"})),
}


def ensure_fixture_role(db, user, role_code: str) -> None:
    from app.core.config import settings
    from app.core.auth_hardening_policy import strict_security_environment
    from app.models import Role, UserRole

    if strict_security_environment(settings):
        raise RuntimeError("Fixture role writes are prohibited in production/staging")
    role_name, allowed_types = _ROLE_TYPES[role_code]
    if (not user.id or not user.tenant_id or user.is_deleted
            or user.status != "ACTIVE" or user.user_type not in allowed_types):
        raise RuntimeError("Fixture account does not match the explicit role contract")
    role = db.scalars(select(Role).where(
        Role.tenant_id == user.tenant_id, Role.role_code == role_code,
    )).one_or_none()
    if role is None:
        role = Role(tenant_id=user.tenant_id, role_code=role_code,
                    role_name=role_name, role_type="SYSTEM", status="ACTIVE")
        db.add(role)
        db.flush()
    elif role.is_deleted or role.status not in {"ACTIVE", "ENABLED"} or role.role_type != "SYSTEM":
        raise RuntimeError("Existing fixture role is withdrawn or not SYSTEM; refusing to overwrite")
    link = db.scalars(select(UserRole).where(
        UserRole.tenant_id == user.tenant_id, UserRole.user_id == user.id,
        UserRole.role_id == role.id,
    )).one_or_none()
    if link is None:
        db.add(UserRole(tenant_id=user.tenant_id, user_id=user.id,
                        role_id=role.id, status="ACTIVE"))
    elif link.is_deleted or link.status != "ACTIVE":
        raise RuntimeError("Existing fixture assignment was withdrawn; refusing to reactivate")
