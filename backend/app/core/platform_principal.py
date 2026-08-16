"""Canonical Platform Principal / permission-plane boundary.

A school-side wildcard is never evidence of a platform identity.  Platform
permission checks must prove the identity plane first and only then evaluate
``platform.*`` permission codes.
"""
from __future__ import annotations

from enum import Enum

from fastapi import Depends, Request

from app.core.exceptions import no_permission
from app.core.permissions import enforce_permission
from app.core.security import get_current_user


class PermissionPlane(str, Enum):
    TENANT = "TENANT"
    PLATFORM = "PLATFORM"


PLATFORM_ROOT_ROLES = frozenset({"PLATFORM_SUPER_ADMIN", "PLATFORM_OWNER"})


def platform_role_of(user: dict | None) -> str:
    """Resolve only a signed platform-plane identity; school roles return empty."""
    user = user or {}
    for raw in (user.get("currentRoleCode"), user.get("userType")):
        role = str(raw or "").strip().upper()
        if role.startswith("PLATFORM_"):
            return role
    return ""


def principal_plane(user: dict | None) -> PermissionPlane:
    return PermissionPlane.PLATFORM if platform_role_of(user) else PermissionPlane.TENANT


def is_platform_principal(user: dict | None) -> bool:
    return bool(platform_role_of(user))


def assert_platform_principal(user: dict | None) -> dict:
    if not is_platform_principal(user):
        raise no_permission("学校身份禁止访问平台控制面")
    return dict(user or {})


def assert_platform_root(user: dict | None) -> dict:
    actor = assert_platform_principal(user)
    if platform_role_of(actor) not in PLATFORM_ROOT_ROLES:
        raise no_permission("该操作仅限平台根职责")
    return actor


def permission_plane(permission_code: str) -> PermissionPlane:
    code = str(permission_code or "").strip()
    return PermissionPlane.PLATFORM if code.startswith("platform.") else PermissionPlane.TENANT


def assert_platform_permission(user: dict | None, permission_code: str) -> dict:
    if permission_plane(permission_code) is not PermissionPlane.PLATFORM:
        raise ValueError(f"platform gate cannot consume non-platform permission: {permission_code}")
    actor = assert_platform_principal(user)
    return enforce_permission(actor, permission_code)


def require_platform_principal(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    return assert_platform_principal(user)


def require_platform_root(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    return assert_platform_root(user)


def require_platform_permission(permission_code: str):
    if permission_plane(permission_code) is not PermissionPlane.PLATFORM:
        raise ValueError(f"platform permission must start with platform.: {permission_code}")

    def _dep(user: dict = Depends(require_platform_principal)) -> dict:
        return assert_platform_permission(user, permission_code)

    return _dep
