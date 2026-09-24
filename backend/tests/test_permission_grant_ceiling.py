import pytest

from app.core import permissions
from app.core.exceptions import AppException


def _catalog(monkeypatch):
    monkeypatch.setattr(
        "app.core.school_admin_permission_resolver.catalog_school_admin_permissions",
        lambda: {
            "systemAdmin.role.view",
            "systemAdmin.role.config",
            "studentAffairs.student.view",
            "studentAffairs.student.manage",
        },
    )


def test_grant_ceiling_allows_only_actor_base_permissions(monkeypatch):
    _catalog(monkeypatch)
    monkeypatch.setattr(
        permissions,
        "get_base_permission_patterns",
        lambda _user: ["studentAffairs.student.view"],
    )

    permissions.assert_delegable_permission_codes(
        {"roleCode": "CUSTOM_RESTRICTED"},
        ["studentAffairs.student.view"],
    )

    with pytest.raises(AppException) as caught:
        permissions.assert_delegable_permission_codes(
            {"roleCode": "CUSTOM_RESTRICTED"},
            ["studentAffairs.student.manage"],
        )
    assert caught.value.code == "NO_PERMISSION"


def test_grant_ceiling_expands_patterns_before_comparing(monkeypatch):
    _catalog(monkeypatch)
    monkeypatch.setattr(
        permissions,
        "get_base_permission_patterns",
        lambda _user: ["studentAffairs.student.view"],
    )

    with pytest.raises(AppException) as caught:
        permissions.assert_delegable_permission_codes(
            {"roleCode": "CUSTOM_RESTRICTED"},
            ["studentAffairs.student.*"],
        )
    assert caught.value.details["codes"] == ["studentAffairs.student.manage"]


def test_temporary_delegation_never_raises_permanent_grant_ceiling(monkeypatch):
    _catalog(monkeypatch)
    monkeypatch.setattr(
        permissions,
        "get_base_permission_patterns",
        lambda _user: ["studentAffairs.student.view"],
    )
    monkeypatch.setattr(
        "app.services.system_governance_service.active_delegation_permission_patterns",
        lambda _user: ["studentAffairs.student.manage"],
    )
    actor = {"roleCode": "CUSTOM_RESTRICTED"}

    assert permissions.has_permission(actor, "studentAffairs.student.manage") is True
    with pytest.raises(AppException):
        permissions.assert_delegable_permission_codes(
            actor,
            ["studentAffairs.student.manage"],
        )
