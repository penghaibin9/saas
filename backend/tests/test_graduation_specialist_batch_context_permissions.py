"""Regression lock for graduation specialist workspace bootstrap permissions.

Every staff graduation page loads the current graduation batch before rendering the
business workspace. Specialist roles therefore need batch *read* context, but must
not inherit any batch management capability.
"""
from __future__ import annotations

import pytest

from app.core.permissions import ROLE_PERMISSIONS
from app.services.system_role_shadow_service import expected_system_role_permissions


SPECIALIST_ROLES = (
    "GD_REVIEWER",
    "GD_DEFENSE_SECRETARY",
    "GD_DEFENSE_EXPERT",
    "GD_GRADE_ADMIN",
)

BATCH_WRITE_PERMISSIONS = {
    "graduationDesign.batch.create",
    "graduationDesign.batch.update",
    "graduationDesign.batch.start",
    "graduationDesign.batch.close",
    "graduationDesign.batch.archive",
}


@pytest.mark.parametrize("role_code", SPECIALIST_ROLES)
def test_graduation_specialist_roles_can_read_batch_context_only(role_code: str):
    patterns = set(ROLE_PERMISSIONS[role_code])
    assert "graduationDesign.batch.view" in patterns
    assert not BATCH_WRITE_PERMISSIONS.intersection(patterns)


@pytest.mark.parametrize("role_code", SPECIALIST_ROLES)
def test_published_system_role_snapshot_includes_batch_read_not_batch_writes(role_code: str):
    permissions = set(expected_system_role_permissions(role_code))
    assert "graduationDesign.batch.view" in permissions
    assert not BATCH_WRITE_PERMISSIONS.intersection(permissions)
