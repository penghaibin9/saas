"""Containment is targeted, fail-closed and committed with its audit evidence.

Deterministic unit cases are separate from the final isolated-MySQL transaction
cases. No test operates on real school accounts or re-enables any subject.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _subject(**changes):
    fields = dict(id=7, tenant_id=11, version=3, user_type="TEACHER", status="ACTIVE",
                  is_deleted=False, wx_openid="test-old-binding", must_change_password=False)
    fields.update(changes)
    return SimpleNamespace(**fields)


class Session:
    def __init__(self, user):
        self.user = user
        self.queries, self.writes = [], []
        self.commits = self.rollbacks = 0

    def scalars(self, statement):
        self.queries.append(statement)
        return SimpleNamespace(one_or_none=lambda: self.user)

    def execute(self, statement):
        self.writes.append(statement)
        return SimpleNamespace(rowcount=2)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def _unit(monkeypatch, user=None):
    from app.services import audit_log, auth_service_db, account_compromise_service as service
    events = []
    monkeypatch.setattr(auth_service_db, "force_subject_revalidation", lambda *a: events.append(("force", a)))
    monkeypatch.setattr(audit_log, "record_critical_in_session", lambda db, action, target, **kw:
                        events.append(("audit", db, action, kw)))
    return service, Session(user or _subject()), events


def _contain(service, db, **changes):
    params = dict(tenant_id=11, user_id=7, expected_version=3, incident_ref="INC-TEST", operator="os:tester")
    params.update(changes)
    return service.contain_in_session(db, **params)


def test_containment_changes_both_binding_sources_and_refresh_in_callers_transaction(monkeypatch):
    service, db, events = _unit(monkeypatch)
    result = _contain(service, db)
    assert (db.user.status, db.user.wx_openid, db.user.version) == ("DISABLED", None, 4)
    assert db.user.must_change_password and not result["reactivated"]
    assert result["wxBindingsDisabled"] == result["refreshRevoked"] == 2
    assert db.commits == 0 and len(db.writes) == 2
    assert events[0] == ("force", ("db-7", 11))
    assert events[1][0:3] == ("audit", db, "ACCOUNT_COMPROMISE_CONTAINED")
    query = str(db.queries[0].compile(compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE" in query and "tenant_id = 11" in query
    writes = [str(s.compile(compile_kwargs={"literal_binds": True})) for s in db.writes]
    assert "tenant_id = 11" in writes[0] and "user_id = 7" in writes[0]
    assert "'db-7'" in writes[1]
    assert "test-old-binding" not in json.dumps(events[1][3])


@pytest.mark.parametrize("changes", [
    {"tenant_id": 0}, {"user_id": -1}, {"expected_version": -1},
    {"user_id": True}, {"incident_ref": "   "}, {"operator": " "},
])
def test_invalid_containment_request_has_no_side_effects(monkeypatch, changes):
    service, db, events = _unit(monkeypatch)
    with pytest.raises(ValueError):
        _contain(service, db, **changes)
    assert not db.writes and not db.queries and not events


@pytest.mark.parametrize("kind", ["PLATFORM_SUPER_ADMIN", "PLATFORM_OP", " platform_owner "])
def test_platform_subject_cannot_be_disabled_by_school_containment(monkeypatch, kind):
    from app.core.exceptions import AppException
    service, db, events = _unit(monkeypatch, _subject(user_type=kind))
    with pytest.raises(AppException) as exc:
        _contain(service, db)
    assert exc.value.http_status == 403
    assert db.user.status == "ACTIVE" and not db.writes and not events


def test_version_conflict_cannot_disable_a_newer_account(monkeypatch):
    from app.core.exceptions import AppException
    service, db, events = _unit(monkeypatch)
    with pytest.raises(AppException) as exc:
        _contain(service, db, expected_version=2)
    assert exc.value.http_status == 409 and not db.writes and not events


def test_force_revalidation_failure_precedes_all_mutations(monkeypatch):
    from app.services import auth_service_db
    service, db, events = _unit(monkeypatch)
    def fail(*args):
        raise RuntimeError("injected shared-store outage")
    monkeypatch.setattr(auth_service_db, "force_subject_revalidation", fail)
    with pytest.raises(RuntimeError):
        _contain(service, db)
    assert db.user.status == "ACTIVE" and not db.writes and not events


def test_missing_tenant_scoped_subject_has_no_mutation(monkeypatch):
    from app.core.exceptions import AppException
    service, db, events = _unit(monkeypatch)
    db.user = None
    with pytest.raises(AppException) as exc:
        _contain(service, db)
    assert exc.value.http_status == 404 and not db.writes and not events


def test_mandatory_audit_failure_propagates_without_internal_commit(monkeypatch):
    from app.services import audit_log
    service, db, events = _unit(monkeypatch)
    def fail(*args, **kwargs):
        raise RuntimeError("injected audit failure")
    monkeypatch.setattr(audit_log, "record_critical_in_session", fail)
    with pytest.raises(RuntimeError, match="audit failure"):
        _contain(service, db)
    assert db.commits == 0  # The caller must roll back; the MySQL cases prove this.


def _cli():
    path = Path(__file__).resolve().parents[1] / "scripts/security_account_control.py"
    spec = importlib.util.spec_from_file_location("pr265_account_control", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_containment_cli_defaults_to_inspection_and_rejects_implicit_writes():
    cli = _cli()
    args = cli.parser().parse_args(["--tenant-code", "school", "--user-id", "7"])
    assert args.action == "inspect" and not args.apply
    with pytest.raises(SystemExit) as exc:
        cli.main(["--tenant-code", "school", "--user-id", "7", "--action", "contain"])
    assert exc.value.code == 2


def test_post_commit_cache_failure_is_recovery_not_business_retry(monkeypatch):
    from app.services import auth_service_db
    cli = _cli()
    def fail(*args):
        raise RuntimeError("injected cache failure")
    monkeypatch.setattr(auth_service_db, "invalidate_subject_cache", fail)
    assert cli._invalidate_after_commit(7, 11) is True


@pytest.mark.parametrize("audit_failure", [False, True])
def test_mysql_containment_audit_atomicity_and_other_tenant_untouched(db_mode, monkeypatch, audit_failure):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import AuthRefreshToken, SecurityAuditLog, Tenant, User, WxAccountBinding
    from app.services import account_compromise_service as service, audit_log, auth_service_db

    owner_tid, other_tid = 1000000000000000001, 2200265
    victim_id, other_id = 8102651, 8102652
    with get_sessionmaker()() as db:
        db.add(Tenant(id=other_tid, tenant_code="pr265-other", school_name="隔离测试学校",
                      deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE"))
        for uid, tid, key in [(victim_id, owner_tid, "a"), (other_id, other_tid, "b")]:
            db.add(User(id=uid, tenant_id=tid, login_name="pr265-victim" if key == "a" else "pr265-other",
                        real_name="测试账号", password_hash="not-a-real-credential", user_type="TEACHER",
                        status="ACTIVE", version=3, wx_openid="pr265-legacy-" + key))
            db.add(WxAccountBinding(tenant_id=tid, user_id=uid, wx_openid="pr265-binding-" + key,
                                    status="ACTIVE"))
            db.add(AuthRefreshToken(token_hash=key * 64, user_id=f"db-{uid}", claims_json={},
                                    expires_at=datetime.utcnow() + timedelta(minutes=10)))
        db.commit()

    # Inject only the external cache dependency. MySQL mutations and normal
    # audit persistence are real; separate unit cases prove cache failure stops writes.
    monkeypatch.setattr(auth_service_db, "force_subject_revalidation", lambda *a: None)
    class InjectedAuditFailure(RuntimeError):
        pass
    if audit_failure:
        def fail(*a, **kw):
            raise InjectedAuditFailure()
        monkeypatch.setattr(audit_log, "record_critical_in_session", fail)
    with get_sessionmaker()() as db:
        if audit_failure:
            with pytest.raises(InjectedAuditFailure):
                service.contain_in_session(db, tenant_id=owner_tid, user_id=victim_id,
                    expected_version=3, incident_ref="INC-PR265", operator="os:pytest")
            db.rollback()
        else:
            service.contain_in_session(db, tenant_id=owner_tid, user_id=victim_id,
                expected_version=3, incident_ref="INC-PR265", operator="os:pytest")
            db.commit()

    with get_sessionmaker()() as db:
        victim, other = db.get(User, victim_id), db.get(User, other_id)
        own_link = db.scalars(select(WxAccountBinding).where(WxAccountBinding.user_id == victim_id)).one()
        other_link = db.scalars(select(WxAccountBinding).where(WxAccountBinding.user_id == other_id)).one()
        own_refresh = db.scalars(select(AuthRefreshToken).where(AuthRefreshToken.user_id == f"db-{victim_id}")).first()
        other_refresh = db.scalars(select(AuthRefreshToken).where(AuthRefreshToken.user_id == f"db-{other_id}")).first()
        audits = db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == owner_tid, SecurityAuditLog.action == "ACCOUNT_COMPROMISE_CONTAINED",
        )).all()
        assert other.status == "ACTIVE" and other.wx_openid == "pr265-legacy-b" and other.version == 3
        assert other_link.status == "ACTIVE" and other_refresh is not None
        if audit_failure:
            assert victim.status == "ACTIVE" and victim.wx_openid == "pr265-legacy-a" and victim.version == 3
            assert own_link.status == "ACTIVE" and own_refresh is not None and not audits
        else:
            assert victim.status == "DISABLED" and victim.wx_openid is None and victim.version == 4
            assert own_link.status == "DISABLED" and own_refresh is None and len(audits) == 1
