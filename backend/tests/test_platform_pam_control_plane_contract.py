from datetime import datetime, timedelta

from app.modules.platform.services import platform_access_governance_service as pam


def test_support_scope_catalog_rejects_unknown_and_wildcard():
    assert "*" not in pam.SUPPORT_SCOPE_CATALOG
    assert "tenant.context.read" in pam.SUPPORT_SCOPE_CATALOG
    assert "tenant.audit.read" in pam.SUPPORT_SCOPE_CATALOG


def test_support_runtime_enforcement_rejects_wrong_operator_tenant_scope_and_expiry():
    now = datetime.utcnow()
    base = {
        "status": "ACTIVE", "operatorUserId": "p-1", "tenantId": "7",
        "incidentId": "1", "scopes": ["tenant.context.read"],
        "expiresAt": (now + timedelta(minutes=10)).isoformat(timespec="seconds"),
    }
    user = {"currentRoleCode": "PLATFORM_DELIVERY", "userId": "p-1"}
    assert pam.support_session_allows(base, user=user, tenant_id=7, scope="tenant.context.read", now=now)
    assert not pam.support_session_allows(base, user={**user, "userId": "p-2"}, tenant_id=7, scope="tenant.context.read", now=now)
    assert not pam.support_session_allows(base, user=user, tenant_id=8, scope="tenant.context.read", now=now)
    assert not pam.support_session_allows(base, user=user, tenant_id=7, scope="tenant.audit.read", now=now)
    assert not pam.support_session_allows({**base, "expiresAt": (now - timedelta(seconds=1)).isoformat()}, user=user, tenant_id=7, scope="tenant.context.read", now=now)


def test_platform_pam_critical_actions_are_registered():
    from app.services import audit_log
    for action in ("PLATFORM_DUTY_CHANGE", "PLATFORM_ELEVATION_CHANGE", "PLATFORM_SUPPORT_SESSION_CHANGE", "PLATFORM_ACCESS_REVIEW_CHANGE"):
        assert action in audit_log.CRITICAL_ACTIONS
