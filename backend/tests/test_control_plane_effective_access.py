from pathlib import Path

import app.core.effective_access as effective_access
from app.core.effective_access import (
    CAMPAIGN_NOT_ACCEPTED,
    ENTERPRISE_MEMBER_INACTIVE,
    GRANT_EXPIRED,
    MODULE_NOT_ENTITLED,
    PERMISSION_DENIED,
    RESOURCE_SCOPE_DENIED,
    STATE_NOT_ALLOWED,
    WRONG_COMPANY,
    explain_enterprise_access,
)
from app.core.platform_principal import PermissionPlane


def _enterprise_facts(**overrides):
    facts = {
        "enterprisePrincipal": True,
        "moduleEntitled": True,
        "permissionAllowed": True,
        "memberStatus": "ACTIVE",
        "grantStatus": "ACTIVE",
        "campaignStatus": "ACCEPTED",
        "companyMatches": True,
        "resourceScopeAllowed": True,
        "stateAllowed": True,
    }
    facts.update(overrides)
    return facts


def test_enterprise_access_explain_has_required_fail_closed_order():
    cases = [
        ({"moduleEntitled": False}, MODULE_NOT_ENTITLED),
        ({"permissionAllowed": False}, PERMISSION_DENIED),
        ({"memberStatus": "DISABLED"}, ENTERPRISE_MEMBER_INACTIVE),
        ({"grantStatus": "EXPIRED"}, GRANT_EXPIRED),
        ({"campaignStatus": "INVITED"}, CAMPAIGN_NOT_ACCEPTED),
        ({"companyMatches": False}, WRONG_COMPANY),
        ({"resourceScopeAllowed": False}, RESOURCE_SCOPE_DENIED),
        ({"stateAllowed": False}, STATE_NOT_ALLOWED),
    ]
    for override, reason in cases:
        result = explain_enterprise_access(facts=_enterprise_facts(**override))
        assert result["allowed"] is False
        assert result["reasonCode"] == reason


def test_enterprise_access_explain_only_allows_all_true_domain_facts():
    result = explain_enterprise_access(facts=_enterprise_facts())
    assert result["allowed"] is True
    assert result["reasonCode"] == "ALLOW"


def test_effective_access_core_does_not_import_e_authority():
    source = (Path(__file__).resolve().parents[1] / "app/core/effective_access.py").read_text(encoding="utf-8")
    assert "app.modules.internship" not in source
    assert "InternshipEnterprise" not in source


def test_module_access_failure_never_produces_cacheable_context(monkeypatch):
    monkeypatch.setattr(
        effective_access,
        "get_effective_access_context",
        lambda _actor: {
            "roleCode": "SCHOOL_ADMIN",
            "permissionPatterns": ["systemAdmin.role.view"],
            "permissionVersion": "perm-v7",
            "moduleStates": {},
            "moduleEntitlements": None,
            "moduleAccessHealthy": False,
            "moduleAccessError": "module authority unavailable",
            "dataScope": {"type": "TENANT_ALL"},
        },
    )
    monkeypatch.setattr(effective_access, "_security_revision", lambda _tenant_id: (19, True, ""))
    monkeypatch.setattr(effective_access, "principal_plane", lambda _actor: PermissionPlane.TENANT)

    context = effective_access.build_effective_access_context({"tenantId": "9001", "userId": "42"})

    assert context["moduleAccessHealthy"] is False
    assert context["cacheable"] is False
    assert context["ctxKey"] is None
    assert context["securityRevisionHealthy"] is True


def test_healthy_module_and_security_context_remains_cacheable(monkeypatch):
    monkeypatch.setattr(
        effective_access,
        "get_effective_access_context",
        lambda _actor: {
            "roleCode": "SCHOOL_ADMIN",
            "permissionPatterns": ["systemAdmin.role.view"],
            "permissionVersion": "perm-v7",
            "moduleStates": {"internship": "ACTIVE"},
            "moduleEntitlements": ["internship"],
            "moduleAccessHealthy": True,
            "moduleAccessError": "",
            "dataScope": {"type": "TENANT_ALL"},
        },
    )
    monkeypatch.setattr(effective_access, "_security_revision", lambda _tenant_id: (19, True, ""))
    monkeypatch.setattr(effective_access, "principal_plane", lambda _actor: PermissionPlane.TENANT)

    context = effective_access.build_effective_access_context({"tenantId": "9001", "userId": "42"})

    assert context["cacheable"] is True
    assert isinstance(context["ctxKey"], str)
    assert len(context["ctxKey"]) == 32
