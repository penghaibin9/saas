"""B0 Platform Principal: school wildcard can never cross the identity plane."""
from __future__ import annotations

import pytest

from app.core.platform_principal import (
    PermissionPlane,
    assert_platform_permission,
    is_platform_principal,
    permission_plane,
    principal_plane,
)


def test_school_admin_wildcard_is_still_tenant_plane():
    actor = {"currentRoleCode": "SCHOOL_ADMIN", "userType": "SCHOOL_ADMIN"}
    assert not is_platform_principal(actor)
    assert principal_plane(actor) is PermissionPlane.TENANT


def test_platform_workforce_identity_is_platform_plane():
    actor = {"currentRoleCode": "PLATFORM_OPERATIONS", "userType": "PLATFORM_OP"}
    assert is_platform_principal(actor)
    assert principal_plane(actor) is PermissionPlane.PLATFORM


def test_platform_permission_namespace_is_explicit():
    assert permission_plane("platform.tenant.view") is PermissionPlane.PLATFORM
    assert permission_plane("systemAdmin.role.manage") is PermissionPlane.TENANT


def test_school_admin_cannot_consume_platform_permission_even_with_wildcard():
    actor = {"currentRoleCode": "SCHOOL_ADMIN", "userType": "SCHOOL_ADMIN"}
    with pytest.raises(Exception):
        assert_platform_permission(actor, "platform.tenant.view")


def test_platform_gate_refuses_non_platform_permission_namespace():
    actor = {"currentRoleCode": "PLATFORM_OWNER", "userType": "PLATFORM_OP"}
    with pytest.raises(ValueError):
        assert_platform_permission(actor, "systemAdmin.role.manage")
