from datetime import datetime, timedelta
import time

import pytest

from app.core.exceptions import AppException
from app.services import platform_access_governance_service as access_governance
from app.services.platform_access_governance_service import (
    assert_platform_capability,
    effective_platform_duties,
    save_access_assignment,
    support_session_allows,
)


def _actor(user_id: int = 8, *, mfa: bool = True) -> dict:
    return {
        "userId": str(user_id),
        "currentRoleCode": "PLATFORM_OPERATIONS",
        "userType": "PLATFORM_OPERATIONS",
        "authTime": int(time.time()),
        "amr": ["pwd", "mfa"] if mfa else ["pwd"],
        "acr": "urn:mfa" if mfa else "urn:pwd",
    }


def test_platform_duties_are_separate_and_commercial_is_not_technical_admin():
    user = {"userId": 1, "currentRoleCode": "PLATFORM_COMMERCIAL"}
    duties = effective_platform_duties(user, assignments=[], elevations=[])
    assert "commercial.manage" in duties
    assert "operations.manage" not in duties
    assert "audit.view" not in duties
    assert_platform_capability(user, "commercial.manage", elevations=[])
    with pytest.raises(Exception):
        assert_platform_capability(user, "operations.manage", elevations=[])


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
        assert_platform_capability(school_admin, "tenant.view", elevations=[])


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
    active = {
        "userId": 9,
        "status": "ACTIVE",
        "capabilities": ["operations.manage"],
        "startsAt": (now - timedelta(minutes=1)).isoformat(),
        "expiresAt": (now + timedelta(minutes=1)).isoformat(),
    }
    expired = {**active, "expiresAt": (now - timedelta(seconds=1)).isoformat()}
    assert "operations.manage" in effective_platform_duties(user, now=now, elevations=[active], assignments=[])
    assert "operations.manage" not in effective_platform_duties(user, now=now, elevations=[expired], assignments=[])


def test_browser_cannot_forge_elevation_approver(monkeypatch):
    from app.modules.platform.services import platform_access_governance_service as base

    monkeypatch.setattr(
        base,
        "_save_atomic",
        lambda config_type, payload, **kwargs: {"configType": config_type, **payload},
    )
    result = base.create_elevation(
        {
            "requestId": "browser-forge-elev-0001",
            "userId": "9",
            "capabilities": ["operations.manage"],
            "durationMinutes": 30,
            "reason": "处理生产事件临时提升",
            "approvedBy": "伪造批准人",
            "approvedByUserId": "forged-user",
        },
        actor=_actor(8),
    )
    assert result["approvedBy"] == "8"
    assert isinstance(result["approvalEvidence"], dict)
    assert result["approvalEvidence"]["recent"] is True
    assert result.get("approvedByUserId") is None


def test_support_access_requires_live_ticket_tenant_scope_operator_and_expiry(monkeypatch):
    runtime = access_governance._canonical
    monkeypatch.setattr(
        runtime,
        "_validate_support_ticket",
        lambda tenant_id, ticket_id, user: {
            "ticketId": str(ticket_id),
            "tenantId": str(tenant_id),
            "status": "OPEN",
            "severity": "P1",
            "assigneeUserId": str(user.get("userId")),
            "version": 1,
        },
    )
    user = _actor(8)
    now = datetime.utcnow()
    session = {
        "operatorUserId": "8",
        "tenantId": 100,
        "status": "ACTIVE",
        "ticketId": "1001",
        "scopes": ["file.metadata.read"],
        "expiresAt": (now + timedelta(minutes=20)).isoformat(),
    }
    assert support_session_allows(session, user=user, tenant_id=100, scope="file.metadata.read", now=now)
    assert not support_session_allows({**session, "ticketId": None}, user=user, tenant_id=100, scope="file.metadata.read", now=now)
    assert not support_session_allows(session, user=user, tenant_id=101, scope="file.metadata.read", now=now)
    assert not support_session_allows(session, user=user, tenant_id=100, scope="sensitive.identity.read", now=now)
    assert not support_session_allows(
        session,
        user={"userId": 8, "currentRoleCode": "SCHOOL_ADMIN"},
        tenant_id=100,
        scope="file.metadata.read",
        now=now,
    )


def test_stored_assignment_grants_only_its_registered_duty():
    user = {"userId": 21, "currentRoleCode": "PLATFORM_STAFF", "userType": "PLATFORM_STAFF"}
    assignment = {"userId": 21, "dutyCode": "PLATFORM_COMMERCIAL", "status": "ACTIVE"}
    duties = effective_platform_duties(user, assignments=[assignment], elevations=[])
    assert "commercial.view" in duties
    assert "operations.manage" not in duties


def test_support_scope_never_accepts_wildcard(monkeypatch):
    runtime = access_governance._canonical
    monkeypatch.setattr(runtime, "_validate_support_ticket", lambda *args, **kwargs: {"status": "OPEN"})
    user = _actor(8)
    now = datetime.utcnow()
    wildcard = {
        "operatorUserId": "8",
        "tenantId": 100,
        "status": "ACTIVE",
        "ticketId": "1001",
        "scopes": ["*"],
        "expiresAt": (now + timedelta(minutes=20)).isoformat(),
    }
    assert support_session_allows(wildcard, user=user, tenant_id=100, scope="tenant.context.read", now=now) is False


def test_root_platform_duties_cannot_be_assigned_through_normal_form():
    with pytest.raises(AppException):
        save_access_assignment(
            {
                "requestId": "root-duty-deny-0001",
                "userId": "31",
                "dutyCode": "PLATFORM_OWNER",
                "reason": "禁止普通表单授予根平台权限",
            },
            actor=_actor(),
        )


def test_access_assignment_requires_auditable_reason_before_storage():
    with pytest.raises(AppException):
        save_access_assignment(
            {
                "requestId": "short-reason-duty-0001",
                "userId": "31",
                "dutyCode": "PLATFORM_COMMERCIAL",
                "reason": "短",
            },
            actor=_actor(),
        )


def test_pam_elevation_requires_mfa():
    with pytest.raises(AppException) as exc:
        access_governance.create_elevation(
            {
                "requestId": "elev-mfa-required-0001",
                "userId": "31",
                "capabilities": ["operations.manage"],
                "durationMinutes": 30,
                "reason": "生产权限提升验证",
            },
            actor=_actor(mfa=False),
        )
    assert exc.value.code == "PLATFORM_MFA_ASSURANCE_REQUIRED"
