"""Adoption changes ownership, not role identity, membership, scope or grants."""
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from app.core.exceptions import AppException
from app.models import CustomRoleSource, RolePermission
from app.modules.system_admin.services import school_role_adoption_service as service
from app.modules.system_admin.routers import system_router as router
from app.services import auth_service_db, saas_role_service


@pytest.fixture
def setup(monkeypatch):
    role = SimpleNamespace(id=81, tenant_id=1007, role_code="ACADEMIC_TEACHER", role_type="SYSTEM",
                           version=4, role_name="学校任课教师", status="ACTIVE", remark="scope=ASSIGNED")
    codes = ("academic.schedule.view",)
    template = SimpleNamespace(template_version=3)
    monkeypatch.setattr(service.shadow, "_latest_published_template", lambda *_: template)
    monkeypatch.setattr(service.shadow, "published_system_role_permissions", lambda *_: codes)
    guard = Mock()
    monkeypatch.setattr(service, "assert_delegable_permission_codes", guard)
    audit = Mock()
    monkeypatch.setattr(service.audit_log, "record_critical_in_session", audit)
    cache = Mock()
    monkeypatch.setattr(auth_service_db, "invalidate_tenant_subject_caches", cache)
    stale = SimpleNamespace(permission_id=99, status="ACTIVE", is_deleted=False)
    db = Mock()
    db.scalars.side_effect = [Mock(first=lambda: role), Mock(first=lambda: None),
                             Mock(all=lambda: [SimpleNamespace(id=91, permission_code=codes[0])]),
                             Mock(all=lambda: [stale])]
    monkeypatch.setattr(router, "get_sessionmaker", lambda: lambda: db)
    monkeypatch.setattr(router, "current_tenant_id", lambda: 1007)
    body = {**service.adoption_preview(db, role), "reason": "保留原成员转由学校维护", "requestId": str(uuid.uuid4())}
    return SimpleNamespace(db=db, role=role, body=body, stale=stale, guard=guard, audit=audit, cache=cache)


def test_adoption_preserves_identity_and_reconciles_stale_links_before_resolver_switch(setup):
    s = setup
    before = vars(s.role).copy()
    result = router.adopt_system_role(81, s.body, user={"id": "1"})["data"]
    assert vars(s.role) == {**before, "role_type": "CUSTOM", "version": 5}
    assert result["cacheInvalidated"] is True
    rows = [call.args[0] for call in s.db.add.call_args_list]
    assert len(rows) == 2 and all(isinstance(row, (RolePermission, CustomRoleSource)) for row in rows)
    assert s.stale.status == "DISABLED" and s.stale.is_deleted is True
    source = next(row for row in rows if isinstance(row, CustomRoleSource))
    assert (source.role_id, source.role_code, source.source_template_version) == (81, "ACADEMIC_TEACHER", 3)
    assert source.permission_codes_json == {"items": ["academic.schedule.view"]}
    assert source.drift_json["automaticUpgrade"] is False
    detail = s.audit.call_args.kwargs["detail"]
    assert detail["beforePermissionDigest"] == detail["afterPermissionDigest"]
    s.guard.assert_called_once_with({"id": "1"}, {"academic.schedule.view", "systemAdmin.role.config"})
    s.db.commit.assert_called_once()


@pytest.mark.parametrize("code", ["SCHOOL_ADMIN", "SYS_ADMIN", "STUDENT", "SECURITY_AUDITOR", "PLATFORM_COMMERCIAL", "UNKNOWN"])
def test_protected_and_non_school_roles_cannot_be_adopted(setup, code):
    s = setup
    s.role.role_code = code
    with pytest.raises(AppException):
        router.adopt_system_role(81, s.body, user={})
    s.db.add.assert_not_called()
    s.db.commit.assert_not_called()


@pytest.mark.parametrize("field", ["expectedVersion", "expectedTemplateVersion", "expectedTemplateDigest"])
def test_stale_preview_rejected_without_writes(setup, field):
    s = setup
    s.body[field] = "stale"
    with pytest.raises(AppException) as exc:
        router.adopt_system_role(81, s.body, user={})
    assert exc.value.code == "DATA_CONFLICT"
    s.db.add.assert_not_called()
    s.db.rollback.assert_called_once()


@pytest.mark.parametrize("failure", ["grant", "catalog", "audit", "binding", "missing_role"])
def test_failed_adoption_rolls_back_whole_command(setup, failure):
    s = setup
    if failure == "grant":
        s.guard.side_effect = AppException("NO_PERMISSION", "temporary grant")
    elif failure == "audit":
        s.audit.side_effect = AppException("SERVER_ERROR", "audit unavailable")
    elif failure == "binding":
        s.db.scalars.side_effect = [Mock(first=lambda: s.role), Mock(first=lambda: object())]
    elif failure == "missing_role":
        s.db.scalars.side_effect = [Mock(first=lambda: None)]
    else:
        s.db.scalars.side_effect = [Mock(first=lambda: s.role), Mock(first=lambda: None), Mock(all=lambda: [])]
    with pytest.raises(AppException):
        router.adopt_system_role(81, s.body, user={})
    s.db.commit.assert_not_called()
    s.db.rollback.assert_called_once()
    s.cache.assert_not_called()


def test_post_commit_cache_failure_reports_partial_completion(setup):
    s = setup
    s.cache.side_effect = RuntimeError("cache down")
    assert router.adopt_system_role(81, s.body, user={})["data"]["cacheInvalidated"] is False
    s.db.commit.assert_called_once()
    s.db.rollback.assert_not_called()


def test_duplicate_adoption_cannot_replace_pinned_school_edits(setup):
    s = setup
    s.role.role_type = "CUSTOM"
    with pytest.raises(AppException):
        router.adopt_system_role(81, s.body, user={})
    s.db.add.assert_not_called()


def test_initialization_preserves_adopted_role_and_rejects_unproven_reserved_code(setup, monkeypatch):
    s = setup
    s.role.role_type = "CUSTOM"
    monkeypatch.setattr(saas_role_service, "BUILTIN_ROLE_TEMPLATES", [
        {"roleCode": "ACADEMIC_TEACHER", "defaultScope": "ASSIGNED"}])
    source = SimpleNamespace(source_template_code="ACADEMIC_TEACHER", source_template_version=3,
                             drift_json={"origin": "SCHOOL_ADOPTED_SYSTEM_ROLE", "automaticUpgrade": False})
    s.db.scalars.side_effect = [Mock(all=lambda: [s.role]), Mock(first=lambda: source)]
    before = vars(s.role).copy()
    assert saas_role_service.ensure_builtin_roles(s.db, 1007)["unchanged"] == 1
    assert vars(s.role) == before
    s.db.add.assert_not_called()
    source.drift_json = {}
    s.db.scalars.side_effect = [Mock(all=lambda: [s.role]), Mock(first=lambda: source)]
    with pytest.raises(AppException):
        saas_role_service.ensure_builtin_roles(s.db, 1007)


def test_new_command_is_registered_once_with_config_permission():
    routes = [r for r in router.router.routes if r.path == "/system/roles/{role_id}/adopt"]
    assert len(routes) == 1 and routes[0].methods == {"POST"}
    assert routes[0].dependant.dependencies


def test_adoption_uses_real_critical_writer_and_propagates_storage_failure(monkeypatch):
    from app.services import audit_log, db_service

    db = Mock()
    insert = Mock()
    monkeypatch.setattr(db_service, "audit_insert_in_session", insert)
    result = audit_log.record_critical_in_session(db, "ROLE_ADOPT", "role:81", tenant_id=1007)
    assert result["action"] == "ROLE_ADOPT"
    assert insert.call_args.args[0] is db
    db.commit.assert_not_called()
    insert.side_effect = RuntimeError("audit storage unavailable")
    with pytest.raises(audit_log.AuditPersistenceError):
        audit_log.record_critical_in_session(db, "ROLE_ADOPT", "role:81", tenant_id=1007)
