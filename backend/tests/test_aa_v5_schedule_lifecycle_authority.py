"""正式课表作废/归档复用学校发布责任；真库节点由主控串行执行。"""
from contextlib import contextmanager
from datetime import datetime, timedelta
import importlib
from types import SimpleNamespace

import pytest


EDIT = "academicAffairs.schedule.edit"
ARCHIVE = "academicAffairs.schedule.archive"


@pytest.mark.parametrize("case", ["college", "none", "no-edit", "no-archive", "expired", "other-actor", "valid", "publish-only"])
def test_current_school_schedule_operator_requires_scope_permissions_and_assignment(monkeypatch, case):
    from app.core.exceptions import AppException
    service = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_schedule_service")
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as responsibility
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity

    permissions = {EDIT, ARCHIVE}
    if case == "no-edit":
        permissions.remove(EDIT)
    if case in {"no-archive", "publish-only"}:
        permissions.remove(ARCHIVE)
    scope = {"college": "COLLEGE", "none": "NONE"}.get(case, "TENANT_ALL")
    context = SimpleNamespace(scope_type=scope, permission_codes=permissions)
    monkeypatch.setattr(service, "build_affairs_context", lambda user, db: context)
    monkeypatch.setattr(identity, "_current_user_id", lambda db, user: 123)
    monkeypatch.setattr(responsibility, "resolve_school", lambda db, **kwargs: {
        "resolved": case != "expired", "assigneeUserIds": ["456" if case == "other-actor" else "123"],
    })
    if case in {"valid", "publish-only"}:
        assert service._require_school_schedule_operator(object(), {"userId": "db-123"}, require_archive=case != "publish-only") is context
    else:
        with pytest.raises(AppException) as rejected:
            service._require_school_schedule_operator(object(), {"userId": "db-123"}, require_archive=True)
        assert rejected.value.code == "NO_DATA_SCOPE"


@pytest.mark.parametrize("name", ["publish", "void_and_reissue", "archive"])
def test_public_and_legacy_lifecycle_commands_use_same_guard_before_query(monkeypatch, name):
    from app.core.exceptions import AppException
    legacy = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_schedule_service")
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as public

    @contextmanager
    def session():
        yield object()  # Any query/lock before the shared guard would fail this test.

    calls = []

    def reject(db, user, *, require_archive=False):
        calls.append(require_archive)
        raise AppException("NO_DATA_SCOPE", "学校责任资格已撤销", http_status=403)

    monkeypatch.setattr(legacy, "session", session)
    monkeypatch.setattr(legacy, "_require_school_schedule_operator", reject)
    if name != "publish":
        assert getattr(public, name) is getattr(legacy, name)
    with pytest.raises(AppException, match="学校责任资格已撤销"):
        getattr(public, name)(7, {}, **({"reason": "正式课表需要重新编排"} if name == "void_and_reissue" else {}))
    assert calls == [name != "publish"]


@pytest.mark.parametrize("name", ["void_and_reissue", "archive"])
def test_lifecycle_locks_authority_then_fresh_tenant_batch_and_keeps_audit(monkeypatch, name):
    from sqlalchemy.dialects import mysql
    service = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_schedule_service")
    from app.modules.academic_affairs.services import academic_affairs_schedule_resource_guard as resource
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive

    events, statements = [], []
    batch = SimpleNamespace(id=7, tenant_id=101, term_id=13, status="PUBLISHED")

    class Session:
        def scalars(self, statement):
            events.append("batch")
            statements.append(statement)
            return SimpleNamespace(first=lambda: batch)

        def add(self, row):
            events.append(row.action)

        def commit(self):
            events.append("commit")

    @contextmanager
    def session():
        yield Session()

    monkeypatch.setattr(service, "session", session)
    monkeypatch.setattr(service, "_tid", lambda: 101)
    monkeypatch.setattr(service, "_op", lambda: ("学校责任人", "ACADEMIC_ADMIN", "123"))
    monkeypatch.setattr(service, "_require_school_schedule_operator", lambda *args, **kwargs: events.append("authority"))
    monkeypatch.setattr(resource, "lock_formal_authority", lambda db: events.append("lock"))
    monkeypatch.setattr(archive, "guard_term_writable", lambda db, term_id: events.append("term"))
    monkeypatch.setattr(service, "_audit", lambda db, domain, batch_id, action, detail: events.append("audit:" + action))
    result = getattr(service, name)(7, {}, **({"reason": "正式课表需要重新编排"} if name == "void_and_reissue" else {}))
    assert events[:3] == ["authority", "lock", "batch"]
    assert events[-1] == "commit" and batch.status == result["status"] == "ARCHIVED"
    assert "audit:" + ("VOID_REISSUE" if name == "void_and_reissue" else "ARCHIVE") in events
    statement = statements[0]
    sql = str(statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "tenant_id = 101" in sql and "is_deleted IS false" in sql and "FOR UPDATE" in sql
    assert statement.get_execution_options()["populate_existing"] is True


def _database_identity(login_name):
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import User
    from app.services.auth_service_db import _claims, _role_contexts
    from tests.test_aa_schedule import TID

    with get_sessionmaker()() as db:
        user = db.query(User).filter(User.tenant_id == TID, User.login_name == login_name).one()
        contexts = _role_contexts(db, user)
        role_code = "SCHOOL_ADMIN" if login_name == "school_admin01" else "COLLEGE_ADMIN"
        context = next(row for row in contexts if row["roleCode"] == role_code)
        claims = _claims(db, user, context, contexts, "PC")
    return {"Authorization": "Bearer " + create_access_token(claims)}, claims


def test_mysql_lifecycle_rejects_college_revoked_permission_and_expired_assignment_then_school_closes(client, db_mode):
    from app.core.context import get_tenant, set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import Permission, Role, RolePermission, StaffAssignment, Tenant, User
    legacy = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_schedule_service")
    from tests.support_academic_review_identity import _ensure_permission
    from tests.test_aa_schedule import BASE, TID
    from tests.test_aa_v5_school_schedule_gate import _candidate, _facts, _snapshot

    facts = _facts(client)
    with get_sessionmaker()() as db:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(id=TID, tenant_code="demo", school_name="课表生命周期责任回归", status="ACTIVE"))
        for code in ("SCHOOL_ADMIN", "COLLEGE_ADMIN"):
            role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == code).one()
            role.role_type = "CUSTOM"  # Only this isolated fixture; actual grants must govern revocation.
            permission = _ensure_permission(db, ARCHIVE)
            if not db.query(RolePermission).filter(RolePermission.tenant_id == TID,
                    RolePermission.role_id == role.id, RolePermission.permission_id == permission.id).first():
                db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status="ACTIVE"))
        db.commit()
    facts["school"], school_claims = _database_identity("school_admin01")
    facts["college"], _ = _database_identity("college_admin01")
    batches = [_candidate(client, facts, index) for index in range(2)]
    for batch_id in batches:
        response = client.post(f"{BASE}/schedule-batches/{batch_id}/publish", headers=facts["school"])
        assert response.status_code == 200, response.text
    before = _snapshot(facts)

    def call(name, batch_id, headers):
        return client.post(f"{BASE}/schedule-batches/{batch_id}/{name}", headers=headers,
            json={"reason": "课表生命周期权限回归"} if name == "void-reissue" else None)

    for name in ("void-reissue", "archive"):
        for batch_id in batches:  # Current and another college: archive permission cannot grant school authority.
            response = call(name, batch_id, facts["college"])
            assert response.status_code == 403, response.text
            assert _snapshot(facts) == before

    with get_sessionmaker()() as db:
        school = db.query(User).filter(User.tenant_id == TID, User.login_name == "school_admin01").one()
        assignment = db.query(StaffAssignment).filter(StaffAssignment.tenant_id == TID,
            StaffAssignment.user_id == school.id, StaffAssignment.org_type == "SCHOOL").one()
        assignment_id = assignment.id
        assignment.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    for name in ("void-reissue", "archive"):
        response = call(name, batches[0], facts["school"])
        assert response.status_code == 403, response.text
        assert _snapshot(facts) == before

    with get_sessionmaker()() as db:
        db.get(StaffAssignment, assignment_id).expires_at = None
        role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == "SCHOOL_ADMIN").one()
        grant = db.query(RolePermission).join(Permission, Permission.id == RolePermission.permission_id).filter(
            RolePermission.tenant_id == TID, RolePermission.role_id == role.id, Permission.permission_code == ARCHIVE).one()
        grant_id = grant.id
        grant.status = "DISABLED"
        db.commit()
    for name in ("void-reissue", "archive"):
        response = call(name, batches[0], facts["school"])
        assert response.status_code == 403, response.text
        assert _snapshot(facts) == before
    previous_tenant = get_tenant()
    set_tenant(TID)
    try:
        # Direct callers must be rejected too; the HTTP dependency alone is not a guard.
        for name in ("void_and_reissue", "archive"):
            with pytest.raises(AppException) as rejected:
                getattr(legacy, name)(batches[0], school_claims,
                    **({"reason": "课表生命周期权限回归"} if name == "void_and_reissue" else {}))
            assert rejected.value.code == "NO_DATA_SCOPE"
            assert _snapshot(facts) == before
    finally:
        set_tenant(previous_tenant)
    with get_sessionmaker()() as db:
        db.get(RolePermission, grant_id).status = "ACTIVE"
        db.commit()
    facts["school"], _ = _database_identity("school_admin01")
    for name, batch_id in zip(("void-reissue", "archive"), batches):
        response = call(name, batch_id, facts["school"])
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "ARCHIVED"
        readback = client.get(f"{BASE}/schedule-batches/{batch_id}", headers=facts["school"])
        assert readback.status_code == 200 and readback.json()["data"]["status"] == "ARCHIVED"
    after = _snapshot(facts)
    actions = [row[2] for row in after["audits"]]
    assert actions.count("VOID_REISSUE") == actions.count("ARCHIVE") == 1
    assert len(after["publishes"]) == len(before["publishes"]) + 1
