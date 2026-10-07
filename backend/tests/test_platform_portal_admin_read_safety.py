"""Admin config failures must not look like an editable default configuration."""
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.services import student_portal_service as service


def test_admin_read_propagates_database_failure_but_student_compatibility_is_unchanged(monkeypatch):
    monkeypatch.setattr(service, "db_enabled", lambda: True)
    factory = Mock(side_effect=RuntimeError("injected database unavailable"))
    monkeypatch.setattr(service, "get_sessionmaker", lambda: factory)
    with pytest.raises(AppException):
        service.get_config(1000000000000000001, strict=True)
    assert service.get_config(1000000000000000001)["portalName"] == service.DEFAULT_PORTAL_NAME


def test_admin_read_requires_database_when_disabled(monkeypatch):
    monkeypatch.setattr(service, "db_enabled", lambda: False)
    with pytest.raises(AppException):
        service.get_config(1000000000000000001, strict=True)


def test_admin_route_uses_strict_config_projection(monkeypatch):
    from app.api.v1 import student_portal_admin as router
    reader = Mock(return_value={"enabled": False})
    monkeypatch.setattr(router.sp, "get_config", reader)
    router.get_portal_config(1000000000000000001, {"currentRoleCode": "PLATFORM_OP"})
    reader.assert_called_once_with(1000000000000000001, strict=True)


def test_missing_row_in_healthy_database_still_returns_supported_defaults(db_mode):
    assert service.get_config(1000000000000000951, strict=True)["modules"] == service.DEFAULT_MODULES


def test_successful_save_returns_accepted_values_not_a_second_failing_override_read(db_mode, monkeypatch):
    monkeypatch.setattr(service, "_load_override", Mock(side_effect=RuntimeError("must not reread")))
    out = service.update_config(1000000000000000001, {"enabled": False, "portalName": "保存已接受", "requiredPackage": "trial", "features": {"export": True}})
    assert out["enabled"] is False
    assert out["portalName"] == "保存已接受"
    assert out["features"]["export"] is False
