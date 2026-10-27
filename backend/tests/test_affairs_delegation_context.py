import pytest


@pytest.mark.parametrize("current_role", ["COUNSELOR", "ACADEMIC_ADMIN", "FUNDING_TEACHER"])
@pytest.mark.parametrize("pinned", [False, True])
def test_temporary_funding_permissions_stay_in_the_funding_context(monkeypatch, current_role, pinned):
    from app.services import system_governance_service as gov
    from app.core.permissions import _match
    monkeypatch.setattr(gov, "list_delegations", lambda: [{
        "granteeUserId": "42", "roleCode": "FUNDING_TEACHER", "status": "ACTIVE",
        "effective": True, "expiresAt": "2099-01-01 00:00:00",
        "permissionCodes": ["studentAffairs.funding.project.manage"] if pinned else [],
    }])
    granted = gov.active_delegation_permission_patterns({"userId": "db-42", "currentRoleCode": current_role})
    assert _match("studentAffairs.funding.project.manage", granted) == (current_role == "FUNDING_TEACHER")


def test_historical_temporary_wildcard_cannot_restore_affairs_permissions_in_another_context(monkeypatch):
    from app.services import system_governance_service as gov, system_role_shadow_service as shadow
    from app.core.permissions import ROLE_PERMISSIONS, _match
    monkeypatch.setitem(ROLE_PERMISSIONS, "TEST_OLD_DELEGATION", {"*"})
    monkeypatch.setattr(shadow, "active_tenant_permission_codes", lambda: (
        "studentAffairs.funding.view", "campusService.grant.view", "academicAffairs.course.view"))
    monkeypatch.setattr(gov, "list_delegations", lambda: [{
        "granteeUserId": "42", "roleCode": "TEST_OLD_DELEGATION", "status": "ACTIVE", "effective": True,
    }])
    granted = gov.active_delegation_permission_patterns({"userId": "db-42", "currentRoleCode": "ACADEMIC_TEACHER"})
    assert not _match("studentAffairs.funding.view", granted)
    assert not _match("campusService.grant.view", granted)
    assert _match("academicAffairs.course.view", granted)
    assert gov.active_delegation_permission_patterns({"userId": "db-42", "currentRoleCode": "COUNSELOR"}) == set()
