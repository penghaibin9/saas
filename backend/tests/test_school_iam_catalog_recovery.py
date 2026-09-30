"""Discovery isolation must not weaken explicit template access or authority checks."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.modules.system_admin.policies.role_template_plane import assert_school_role_template_code
from app.modules.system_admin.services import school_iam_authority_projection_service as svc


def template(code, version=1):
    return SimpleNamespace(id=version, template_code=code, template_name=code,
                           template_version=version, template_plane="TENANT",
                           template_category="SYSTEM_ROLE", publish_status="PUBLISHED",
                           permission_digest="", permission_ceiling_json={})


def catalog_session(monkeypatch, rows):
    db = Mock()
    db.scalars.side_effect = [Mock(all=lambda: rows), Mock(all=lambda: [])]
    monkeypatch.setattr(svc, "_tenant_id", lambda: 1000000000000000007)
    monkeypatch.setattr(svc, "get_sessionmaker", lambda: lambda: db)
    return db


def test_mislabelled_non_school_templates_do_not_break_school_discovery(monkeypatch):
    db = catalog_session(monkeypatch, [template("PLATFORM_COMMERCIAL"), template("HR"),
                                      template("SCHOOL_ADMIN", 2), template("SCHOOL_ADMIN"),
                                      template("TEACHER")])
    reader = Mock(return_value=["systemAdmin.role.view"])
    monkeypatch.setattr(svc, "_template_permissions", reader)
    result = svc.template_catalog()
    assert [(r["templateCode"], r["templateVersion"]) for r in result] == [("SCHOOL_ADMIN", 2), ("TEACHER", 1)]
    assert reader.call_count == 2
    db.close.assert_called_once()


@pytest.mark.parametrize("code", ["PLATFORM_COMMERCIAL", "COMPANY_ADMIN", "HR", "MENTOR"])
def test_explicit_non_school_template_access_stays_rejected(code):
    with pytest.raises(AppException) as error:
        assert_school_role_template_code(code)
    assert error.value.code == "ROLE_TEMPLATE_PLANE_VIOLATION"


def test_actual_school_permission_drift_is_not_silently_skipped(monkeypatch):
    db = catalog_session(monkeypatch, [template("SCHOOL_ADMIN")])
    monkeypatch.setattr(svc, "_template_permissions", Mock(side_effect=AppException(
        "B7_TEMPLATE_PERMISSION_DRIFT", "invalid normalized permission", http_status=409)))
    with pytest.raises(AppException) as error:
        svc.template_catalog()
    assert error.value.code == "B7_TEMPLATE_PERMISSION_DRIFT"
    db.close.assert_called_once()


def test_digest_drift_and_missing_normalized_rows_remain_rejected():
    db = Mock()
    db.scalars.return_value.all.return_value = []
    row = template("TEACHER")
    row.permission_ceiling_json = {"items": ["systemAdmin.role.view"]}
    with pytest.raises(AppException) as error:
        svc._template_permissions(db, row)
    assert error.value.code == "B7_NORMALIZED_TEMPLATE_REQUIRED"
    row.permission_ceiling_json = {}
    row.permission_digest = "forged"
    with pytest.raises(AppException) as error:
        svc._template_permissions(db, row)
    assert error.value.code == "B7_TEMPLATE_DIGEST_DRIFT"
