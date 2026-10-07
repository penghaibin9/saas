"""Template initialization uses a pinned snapshot and the existing atomic role write."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.models import CustomRoleSource, Role, RolePermission, UserRole
from app.modules.system_admin.routers import system_router as router
from app.modules.system_admin.services import school_iam_authority_projection_service as projection
from app.services import audit_log, data_scope_service
from app.core import permissions as auth


@pytest.fixture
def setup(monkeypatch):
    template = SimpleNamespace(id=71, template_code="ACADEMIC_TEACHER", template_version=3,
                               permission_digest="reviewed-digest")
    permission = SimpleNamespace(id=81, permission_code="academic.schedule.view")
    db = Mock()
    db.scalars.side_effect = [Mock(first=lambda: None), Mock(first=lambda: template),
                             Mock(all=lambda: [permission])]
    added = []
    def add(row):
        if isinstance(row, Role):
            row.id = 101
        added.append(row)
    db.add.side_effect = add
    monkeypatch.setattr(router, "get_sessionmaker", lambda: lambda: db)
    monkeypatch.setattr(router, "current_tenant_id", lambda: 1007)
    monkeypatch.setattr(router._bundle, "_role_row", lambda role, count: {"id": str(role.id)})
    reader = Mock(return_value=[permission.permission_code])
    monkeypatch.setattr(projection, "_template_permissions", reader)
    guard = Mock()
    monkeypatch.setattr(auth, "assert_delegable_permission_codes", guard)
    monkeypatch.setattr(router, "_assert_custom_role_catalog_policy", Mock())
    scope = Mock()
    monkeypatch.setattr(data_scope_service, "save_role_scope_in_session", scope)
    audit = Mock()
    monkeypatch.setattr(audit_log, "record_critical_in_session", audit)
    body = dict(name="课表查询角色", code="LOCAL_TIMETABLE", sourceTemplateCode="ACADEMIC_TEACHER",
                scopeCode="ASSIGNED", initialPermissions="TEMPLATE", expectedTemplateVersion=3,
                expectedTemplateDigest="reviewed-digest")
    return SimpleNamespace(db=db, added=added, reader=reader, guard=guard, scope=scope,
                           audit=audit, body=body, template=template)


def test_template_creation_pins_real_permissions_and_does_not_assign_members(setup):
    s = setup
    result = router.create_system_role(s.body, user={"userId": "1"})["data"]
    assert result["initialPermissionCount"] == 1
    source = next(row for row in s.added if isinstance(row, CustomRoleSource))
    assert source.source_template_version == 3
    assert source.permission_codes_json == {"items": ["academic.schedule.view"]}
    assert source.drift_json["automaticUpgrade"] is False
    link = next(row for row in s.added if isinstance(row, RolePermission))
    assert (link.tenant_id, link.role_id, link.permission_id) == (1007, 101, 81)
    assert not any(isinstance(row, UserRole) for row in s.added)
    s.guard.assert_called_once_with({"userId": "1"}, {"academic.schedule.view"})
    s.audit.assert_called_once()
    s.db.commit.assert_called_once()
    s.template.template_version = 4
    assert source.source_template_version == 3


@pytest.mark.parametrize("field,value", [("expectedTemplateVersion", None),
                                         ("expectedTemplateVersion", 2),
                                         ("expectedTemplateDigest", "new-digest")])
def test_changed_or_unreviewed_template_is_conflict_without_writes(setup, field, value):
    s = setup
    s.body[field] = value
    with pytest.raises(AppException) as exc:
        router.create_system_role(s.body, user={"userId": "1"})
    assert exc.value.code == "DATA_CONFLICT"
    assert s.added == []
    s.db.commit.assert_not_called()
    s.db.rollback.assert_called_once()


@pytest.mark.parametrize("failure", ["grant", "catalog", "audit"])
def test_grant_catalog_or_audit_failure_cannot_commit_partial_role(setup, failure):
    s = setup
    if failure == "grant":
        s.guard.side_effect = AppException("NO_PERMISSION", "not delegable")
    elif failure == "catalog":
        s.db.scalars.side_effect = [Mock(first=lambda: None), Mock(first=lambda: s.template), Mock(all=lambda: [])]
    else:
        s.audit.side_effect = AppException("SERVER_ERROR", "audit unavailable")
    with pytest.raises(AppException):
        router.create_system_role(s.body, user={"userId": "1"})
    s.db.commit.assert_not_called()
    s.db.rollback.assert_called_once()


def test_legacy_empty_role_creation_does_not_grant_template(setup):
    s = setup
    del s.body["initialPermissions"]
    result = router.create_system_role(s.body, user={"userId": "1"})["data"]
    assert result["initialPermissionCount"] == 0
    assert not any(isinstance(row, RolePermission) for row in s.added)
    s.reader.assert_not_called()


def test_client_permission_list_is_never_used_as_template_authority(setup):
    s = setup
    s.body["permissionCodes"] = ["platform.tenant.manage", "*"]
    router.create_system_role(s.body, user={"userId": "1"})
    source = next(row for row in s.added if isinstance(row, CustomRoleSource))
    assert source.permission_codes_json == {"items": ["academic.schedule.view"]}
