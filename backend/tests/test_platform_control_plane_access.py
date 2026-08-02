from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.services.platform_access_governance_service import (
    assert_platform_capability,
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


def test_temporary_elevation_expires_automatically():
    user = {"userId": 9, "currentRoleCode": "PLATFORM_DELIVERY"}
    now = datetime.utcnow()
    active = {"userId": 9, "status": "ACTIVE", "capabilities": ["operations.manage"],
              "startsAt": (now - timedelta(minutes=1)).isoformat(),
              "expiresAt": (now + timedelta(minutes=1)).isoformat()}
    expired = {**active, "expiresAt": (now - timedelta(seconds=1)).isoformat()}
    assert "operations.manage" in effective_platform_duties(user, now=now, elevations=[active])
    assert "operations.manage" not in effective_platform_duties(user, now=now, elevations=[expired])


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


def test_access_assignment_requires_auditable_reason_before_storage():
    with pytest.raises(AppException):
        save_access_assignment({"userId": "31", "dutyCode": "PLATFORM_COMMERCIAL", "reason": "短"})


def test_support_session_requires_reason_before_storage():
    with pytest.raises(AppException):
        create_support_session({
            "tenantId": 100, "operatorUserId": 8, "ticketId": "T-102",
            "scopes": ["file.metadata"], "durationMinutes": 30, "reason": "短",
        })
