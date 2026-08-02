from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.services import platform_access_governance_service as access_governance
from app.services.platform_access_governance_service import (
    assert_platform_capability,
    create_elevation,
    create_support_session,
    effective_platform_duties,
    save_access_assignment,
    support_session_allows,
)


def test_platform_duties_are_separate_and_commercial_is_not_technical_admin():
    user = {"userId": 1, "currentRoleCode": "PLATFORM_COMMERCIAL"}
    duties = effective_platform_duties(user)
    assert "commercial.manage" in duties
    assert "operations.manage" not in duties
    assert "audit.view" not in duties
    assert_platform_capability(user, "commercial.manage")
    with pytest.raises(Exception):
        assert_platform_capability(user, "operations.manage")


def test_school_admin_wildcard_never_crosses_into_platform_control_plane():
    school_admin = {
        "userId": 7,
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "ADMIN",
        "permissions": ["*"],
    }
    forged_assignment = {
        "userId": 7,
        "dutyCode": "PLATFORM_COMMERCIAL",
        "status": "ACTIVE",
    }
    assert effective_platform_duties(
        school_admin,
        assignments=[forged_assignment],
        elevations=[],
    ) == set()
    with pytest.raises(Exception):
        assert_platform_capability(school_admin, "tenant.view")


def test_platform_user_type_is_not_shadowed_by_a_school_current_role():
    user = {
        "userId": 8,
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "PLATFORM_OPERATIONS",
    }
    duties = effective_platform_duties(user, assignments=[], elevations=[])
    assert "operations.manage" in duties
    assert "commercial.manage" not in duties


def test_temporary_elevation_expires_automatically():
    user = {"userId": 9, "currentRoleCode": "PLATFORM_DELIVERY"}
    now = datetime.utcnow()
    active = {"userId": 9, "status": "ACTIVE", "capabilities": ["operations.manage"],
              "startsAt": (now - timedelta(minutes=1)).isoformat(),
              "expiresAt": (now + timedelta(minutes=1)).isoformat()}
    expired = {**active, "expiresAt": (now - timedelta(seconds=1)).isoformat()}
    assert "operations.manage" in effective_platform_duties(user, now=now, elevations=[active])
    assert "operations.manage" not in effective_platform_duties(user, now=now, elevations=[expired])


def test_browser_cannot_forge_elevation_approver(monkeypatch):
    monkeypatch.setattr(
        access_governance,
        "save_record",
        lambda config_type, payload, **kwargs: {"configType": config_type, **payload},
    )
    result = create_elevation({
        "userId": "9",
        "capabilities": ["operations.manage"],
        "durationMinutes": 30,
        "reason": "处理生产事件临时提升",
        "approvedBy": "伪造批准人",
        "approvedByUserId": "forged-user",
    })
    assert result["approvedBy"] == "AUTHENTICATED_ACCESS_MANAGER"
    assert result["approvalEvidence"] == "SECURITY_AUDIT_CONTEXT"
    assert result.get("approvedByUserId") is None


def test_support_access_requires_ticket_tenant_scope_and_expiry():
    user = {"userId": 8, "currentRoleCode": "PLATFORM_OPERATIONS"}
    now = datetime.utcnow()
    session = {
        "operatorUserId": 8, "tenantId": 100, "status": "ACTIVE",
        "ticketId": "T-100", "scopes": ["file.metadata"],
        "expiresAt": (now + timedelta(minutes=20)).isoformat(),
    }
    assert support_session_allows(session, user=user, tenant_id=100, scope="file.metadata", now=now)
    assert not support_session_allows({**session, "ticketId": None}, user=user, tenant_id=100, scope="file.metadata", now=now)
    assert not support_session_allows(session, user=user, tenant_id=101, scope="file.metadata", now=now)
    assert not support_session_allows(session, user=user, tenant_id=100, scope="file.content", now=now)
    assert not support_session_allows(
        session,
        user={"userId": 8, "currentRoleCode": "SCHOOL_ADMIN"},
        tenant_id=100,
        scope="file.metadata",
        now=now,
    )


def test_stored_assignment_grants_only_its_registered_duty():
    user = {"userId": 21, "currentRoleCode": "PLATFORM_STAFF", "userType": "PLATFORM_STAFF"}
    assignment = {"userId": 21, "dutyCode": "PLATFORM_COMMERCIAL", "status": "ACTIVE"}
    duties = effective_platform_duties(user, assignments=[assignment], elevations=[])
    assert "commercial.view" in duties
    assert "operations.manage" not in duties


def test_support_scope_never_accepts_wildcard():
    user = {"userId": 8, "currentRoleCode": "PLATFORM_OPERATIONS"}
    now = datetime.utcnow()
    wildcard = {
        "operatorUserId": 8, "tenantId": 100, "status": "ACTIVE",
        "ticketId": "T-101", "scopes": ["*"],
        "expiresAt": (now + timedelta(minutes=20)).isoformat(),
    }
    assert support_session_allows(wildcard, user=user, tenant_id=100, scope="file.metadata", now=now) is False


def test_root_platform_duties_cannot_be_assigned_through_normal_form():
    with pytest.raises(AppException):
        save_access_assignment({
            "userId": "31",
            "dutyCode": "PLATFORM_OWNER",
            "reason": "禁止普通表单授予根平台权限",
        })


def test_access_assignment_requires_auditable_reason_before_storage():
    with pytest.raises(AppException):
        save_access_assignment({"userId": "31", "dutyCode": "PLATFORM_COMMERCIAL", "reason": "短"})


def test_support_session_requires_reason_before_storage():
    with pytest.raises(AppException):
        create_support_session({
            "tenantId": 100, "operatorUserId": 8, "ticketId": "T-102",
            "scopes": ["file.metadata"], "durationMinutes": 30, "reason": "短",
        })
