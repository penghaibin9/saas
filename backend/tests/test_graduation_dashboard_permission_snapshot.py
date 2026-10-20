"""Batch permission decisions must read one authority snapshot per request."""
from __future__ import annotations

from app.core import permissions


def test_permission_decisions_share_one_effective_pattern_read(monkeypatch):
    reads: list[dict] = []

    def effective_patterns(user):
        reads.append(user)
        return ["graduationDesign.proposal.*", "graduationDesign.risk.view"]

    monkeypatch.setattr(permissions, "get_effective_permission_patterns", effective_patterns)
    decisions = permissions.permission_decisions({"currentRoleCode": "GD_MENTOR"}, [
        "graduationDesign.proposal.view",
        "graduationDesign.proposal.review",
        "graduationDesign.risk.view",
        "graduationDesign.final.view",
    ])

    assert reads == [{"currentRoleCode": "GD_MENTOR"}]
    assert decisions["graduationDesign.proposal.view"] is True
    assert decisions["graduationDesign.proposal.review"] is True
    assert decisions["graduationDesign.risk.view"] is True
    assert decisions["graduationDesign.final.view"] is False


def test_permission_decisions_keep_canonical_deny_fallback(monkeypatch):
    denied_code = "graduationDesign.risk.close"
    fallbacks: list[str] = []

    monkeypatch.setattr(permissions, "get_effective_permission_patterns", lambda _user: ["graduationDesign.risk.*"])
    monkeypatch.setitem(permissions.ROLE_PERMISSION_DENY, "DASHBOARD_DENY_TEST", {denied_code})
    monkeypatch.setattr(permissions, "has_permission", lambda _user, code: fallbacks.append(code) or False)

    decisions = permissions.permission_decisions({"currentRoleCode": "DASHBOARD_DENY_TEST"}, [
        denied_code,
        "graduationDesign.risk.view",
    ])

    assert fallbacks == [denied_code]
    assert decisions[denied_code] is False
    assert decisions["graduationDesign.risk.view"] is True
