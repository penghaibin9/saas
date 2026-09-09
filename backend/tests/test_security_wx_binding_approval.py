"""Source-unit boundaries for independent WeChat enrollment approval.

Uses session doubles only. Real MySQL/API/row-lock cases are in the companion
*_mysql.py file. Neither suite changes production users or uses SQLite.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from app.core.exceptions import AppException
from app.services import auth_service_db as auth
from app.services import control_plane_auth_service as p0
from app.services import wx_binding_approval_service as approval


def user(**values):
    data = dict(id=7, tenant_id=11, version=3, user_type="TEACHER", status="ACTIVE",
                is_deleted=False, login_name="teacher", password_hash="stored-hash", wx_openid=None)
    data.update(values)
    return SimpleNamespace(**data)


class DB:
    def __init__(self, result=None):
        self.result = result
        self.added = []
        self.calls = []
        self.failure = None

    def scalars(self, statement):
        self.calls.append("select")
        assert statement._for_update_arg is not None
        if self.failure:
            raise self.failure
        return SimpleNamespace(one_or_none=lambda: self.result, first=lambda: self.result)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        self.calls.append("flush")

    def commit(self):
        self.calls.append("commit")

    def rollback(self):
        self.calls.append("rollback")

    def close(self):
        self.calls.append("close")

    def refresh(self, row, **kwargs):
        self.calls.append("lock-user" if kwargs.get("with_for_update") else "refresh")


def grant_row(u=None):
    return SimpleNamespace(
        payload_json={"binding": approval._binding(u or user(), "verified-openid"), "approvalRef": "wxap-test"},
        expires_at=datetime.utcnow() + timedelta(minutes=5), consumed_at=None,
    )


@pytest.fixture
def strict(monkeypatch):
    monkeypatch.setattr(approval, "settings", SimpleNamespace(
        APP_ENV="production", is_prod=True, mock_login_enabled=False,
    ))


@pytest.mark.parametrize("token", [None, ""])
def test_missing_approval_never_uses_password_as_second_factor(strict, token):
    db = DB()
    with pytest.raises(AppException) as exc:
        approval.consume_in_session(db, user(), "verified-openid", token)
    assert exc.value.code == "WX_BIND_APPROVAL_REQUIRED"
    assert not db.calls


@pytest.mark.parametrize("token", ["short", "x" * 129, "!" * 43, 123])
def test_invalid_ticket_shape_is_rejected_before_query(strict, token):
    db = DB()
    with pytest.raises(AppException) as exc:
        approval.consume_in_session(db, user(), "verified-openid", token)
    assert exc.value.code == "WX_BIND_APPROVAL_INVALID" and not db.calls


@pytest.mark.parametrize("field,value", [("id", 8), ("tenant_id", 12), ("version", 4)])
def test_mismatch_never_consumes_other_subject_grant(strict, field, value):
    row = grant_row()
    u = user(**{field: value})
    with pytest.raises(AppException):
        approval.consume_in_session(DB(row), u, "verified-openid", "a" * 43)
    assert row.consumed_at is None


def test_wrong_openid_does_not_consume(strict):
    row = grant_row()
    with pytest.raises(AppException):
        approval.consume_in_session(DB(row), user(), "different-openid", "a" * 43)
    assert row.consumed_at is None


@pytest.mark.parametrize("kind", ["PLATFORM_SUPER_ADMIN", "PLATFORM_OP", "UNKNOWN", ""])
def test_school_channel_rejects_platform_and_unknown_identity(strict, kind):
    with pytest.raises(AppException) as exc:
        approval.consume_in_session(DB(), user(user_type=kind), "verified-openid", "a" * 43)
    assert exc.value.http_status == 403


@pytest.mark.parametrize("values", [{"status": "DISABLED"}, {"is_deleted": True}])
def test_disabled_or_deleted_subject_cannot_consume(strict, values):
    with pytest.raises(AppException) as exc:
        approval.consume_in_session(DB(), user(**values), "verified-openid", "a" * 43)
    assert exc.value.http_status == 401


@pytest.mark.parametrize("expired,consumed", [(True, False), (False, True)])
def test_expired_or_replayed_grant_refused(strict, expired, consumed):
    row = grant_row()
    if expired:
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    if consumed:
        row.consumed_at = datetime.utcnow()
    before = row.consumed_at
    with pytest.raises(AppException):
        approval.consume_in_session(DB(row), user(), "verified-openid", "a" * 43)
    assert row.consumed_at == before


def test_consumption_joins_transaction_and_never_commits(strict):
    row = grant_row()
    db = DB(row)
    assert approval.consume_in_session(db, user(), "verified-openid", "a" * 43) == "wxap-test"
    assert row.consumed_at is not None and db.calls == ["select", "flush"]
    with pytest.raises(AppException):
        approval.consume_in_session(db, user(), "verified-openid", "a" * 43)


def test_database_failure_is_503_not_an_allow_fallback(strict):
    db = DB()
    db.failure = OperationalError("read", {}, RuntimeError("injected"))
    with pytest.raises(AppException) as exc:
        approval.consume_in_session(db, user(), "verified-openid", "a" * 43)
    assert exc.value.http_status == 503


@pytest.mark.parametrize("env,mock,allowed", [("test", True, True), ("test", False, False), ("staging", True, False)])
def test_only_explicit_nonproduction_fixture_may_omit_code(monkeypatch, env, mock, allowed):
    monkeypatch.setattr(approval, "settings", SimpleNamespace(APP_ENV=env, is_prod=False, mock_login_enabled=mock))
    if allowed:
        assert approval.consume_in_session(DB(), user(), "verified-openid", None) is None
    else:
        with pytest.raises(AppException):
            approval.consume_in_session(DB(), user(), "verified-openid", None)


def test_supplied_development_code_is_still_validated(monkeypatch):
    monkeypatch.setattr(approval, "settings", SimpleNamespace(APP_ENV="test", is_prod=False, mock_login_enabled=True))
    with pytest.raises(AppException):
        approval.consume_in_session(DB(), user(), "verified-openid", "a" * 43)


def issue(db, **overrides):
    args = dict(tenant_id=11, user_id=7, expected_version=3, openid="verified-openid",
                incident_ref="TICKET-265", operator="os:tester", identity_verified=True)
    args.update(overrides)
    return approval.issue_in_session(db, **args)


@pytest.fixture
def issuer(monkeypatch):
    from app.services import audit_log
    calls = []
    monkeypatch.setattr(auth, "_ensure_tenant_login_allowed", lambda *a: None)
    monkeypatch.setattr(auth, "_role_contexts", lambda *a: [{"roleCode": "TEACHER"}])
    monkeypatch.setattr(audit_log, "record_critical_in_session", lambda *a, **kw: calls.append((a, kw)))
    return calls


def test_issuer_stores_only_digest_and_requires_caller_commit(strict, issuer):
    db = DB(user())
    ticket = issue(db)
    row = db.added[0]
    assert row.challenge_id_hash == approval._token_hash(ticket["bindingApprovalToken"])
    assert ticket["bindingApprovalToken"] not in json.dumps(row.payload_json)
    assert "verified-openid" not in json.dumps(row.payload_json)
    assert "commit" not in db.calls and len(issuer) == 1
    assert issuer[0][0][1] == "WX_BIND_APPROVAL_AUTHORIZED"
    assert issuer[0][1]["tenant_id"] == 11


@pytest.mark.parametrize("change", [{"identity_verified": False}, {"expected_version": -1}, {"incident_ref": ""}, {"operator": ""}])
def test_issuer_rejects_missing_independent_proof_without_query(strict, change):
    db = DB(user())
    with pytest.raises(AppException):
        issue(db, **change)
    assert not db.calls and not db.added


def test_issuer_rejects_stale_account_version(strict, issuer):
    db = DB(user(version=4))
    with pytest.raises(AppException) as exc:
        issue(db)
    assert exc.value.code == "DATA_CONFLICT" and not db.added


def test_issuer_requires_real_role(strict, issuer, monkeypatch):
    monkeypatch.setattr(auth, "_role_contexts", lambda *a: [])
    db = DB(user())
    with pytest.raises(AppException):
        issue(db)
    assert not db.added


def test_issuer_audit_failure_never_returns_code(strict, issuer, monkeypatch):
    from app.services import audit_log
    monkeypatch.setattr(audit_log, "record_critical_in_session", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("audit")))
    db = DB(user())
    with pytest.raises(RuntimeError):
        issue(db)
    assert "commit" not in db.calls


@pytest.fixture
def runtime(monkeypatch, strict):
    from app.services import audit_log, wx_auth_service
    u = user()
    db = DB()
    calls = []
    monkeypatch.setattr(p0, "db_enabled", lambda: True)
    monkeypatch.setattr(p0, "get_sessionmaker", lambda: lambda: db)
    monkeypatch.setattr(p0, "decode_token", lambda token: {"purpose": "wx_bind", "wxOpenid": "verified-openid"})
    monkeypatch.setattr(auth, "_find_login_user", lambda *a: u)
    monkeypatch.setattr(p0, "resolve_login_policy", lambda **kw: {"loginFailLockMinutes": 15, "captchaAfterFailures": 3})
    monkeypatch.setattr(p0, "_remaining_lock", lambda *a, **kw: 0)
    monkeypatch.setattr(p0, "verify_password", lambda *a: True)
    monkeypatch.setattr(auth, "_ensure_tenant_login_allowed", lambda *a: None)
    monkeypatch.setattr(auth, "_role_contexts", lambda *a: [{"roleCode": "TEACHER"}])
    monkeypatch.setattr(wx_auth_service, "bind_openid_in_session", lambda *a: calls.append("bind"))
    monkeypatch.setattr(p0, "_reset_account_risk", lambda *a, **kw: None)
    monkeypatch.setattr(p0, "build_login_result", lambda *a, **kw: {"userId": "db-7"})
    monkeypatch.setattr(audit_log, "record_critical_in_session", lambda *a, **kw: calls.append("audit"))
    return u, db, calls


def test_actual_runtime_new_binding_rejects_password_only(runtime):
    _, db, calls = runtime
    with pytest.raises(AppException) as exc:
        p0.wx_bind("wx-token", "teacher", "password", "school")
    assert exc.value.code == "WX_BIND_APPROVAL_REQUIRED"
    assert "lock-user" in db.calls and "rollback" in db.calls
    assert not calls and "commit" not in db.calls


def test_actual_runtime_consumes_in_its_own_session(runtime, monkeypatch):
    u, db, calls = runtime
    def consume(session, subject, openid, token):
        assert session is db and subject is u and openid == "verified-openid" and token == "a" * 43
        calls.append("consume")
        return "wxap-test"
    monkeypatch.setattr(approval, "consume_in_session", consume)
    assert p0.wx_bind("wx-token", "teacher", "password", "school", binding_approval_token="a" * 43)["userId"] == "db-7"
    assert calls == ["consume", "bind", "audit"] and db.calls.count("commit") == 1


@pytest.mark.parametrize("legacy", [False, True])
def test_existing_active_identity_does_not_require_new_approval(runtime, legacy, monkeypatch):
    u, db, calls = runtime
    if legacy:
        u.wx_openid = "verified-openid"
    else:
        db.result = SimpleNamespace(user_id=u.id, status="ACTIVE", is_deleted=False)
    monkeypatch.setattr(approval, "consume_in_session", lambda *a: pytest.fail("existing identity must not require a new grant"))
    assert p0.wx_bind("wx-token", "teacher", "password")["userId"] == "db-7"
    assert calls == ["bind", "audit"]


def test_revoked_binding_cannot_reactivate_without_approval(runtime):
    u, db, calls = runtime
    db.result = SimpleNamespace(user_id=u.id, status="DISABLED", is_deleted=False)
    u.wx_openid = "verified-openid"
    with pytest.raises(AppException) as exc:
        p0.wx_bind("wx-token", "teacher", "password")
    assert exc.value.code == "WX_BIND_APPROVAL_REQUIRED" and not calls


def test_deleted_binding_is_not_silently_resurrected(runtime):
    u, db, calls = runtime
    db.result = SimpleNamespace(user_id=u.id, status="ACTIVE", is_deleted=True)
    with pytest.raises(AppException) as exc:
        p0.wx_bind("wx-token", "teacher", "password")
    assert exc.value.code == "DATA_CONFLICT" and not calls


def test_actual_runtime_audit_failure_rolls_back(runtime, monkeypatch):
    from app.services import audit_log
    _, db, calls = runtime
    monkeypatch.setattr(approval, "consume_in_session", lambda *a: "wxap-test")
    monkeypatch.setattr(audit_log, "record_critical_in_session", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("audit")))
    with pytest.raises(RuntimeError):
        p0.wx_bind("wx-token", "teacher", "password", binding_approval_token="a" * 43)
    assert calls == ["bind"] and "rollback" in db.calls and "commit" not in db.calls


def _cli():
    path = Path(__file__).resolve().parents[1] / "scripts/security_wx_approval.py"
    spec = importlib.util.spec_from_file_location("security_wx_cli_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_requires_explicit_write_and_independent_verification(tmp_path):
    cli = _cli()
    with pytest.raises(SystemExit) as exc:
        cli.main(["--tenant-code", "school", "--user-id", "7", "--expected-version", "3",
                  "--incident-ref", "TICKET-265", "--ticket-file", str(tmp_path / "private.json")])
    assert exc.value.code == 2 and not (tmp_path / "private.json").exists()


def test_cli_refuses_echoed_secret_input(monkeypatch):
    import getpass
    import warnings
    cli = _cli()
    def fallback(prompt):
        warnings.warn("would echo", getpass.GetPassWarning)
        return "should-never-return"
    monkeypatch.setattr(cli.getpass, "getpass", fallback)
    with pytest.raises(getpass.GetPassWarning):
        cli._hidden_token()


def test_ticket_namespace_is_distinct_from_captcha_hash():
    import hashlib
    assert approval._token_hash("a" * 43) != hashlib.sha256(("a" * 43).encode()).hexdigest()


@pytest.mark.parametrize("failure", [None, "audit", "commit"])
def test_cli_delivers_only_after_commit_and_does_not_log_code(monkeypatch, tmp_path, capsys, failure):
    from app.core import config
    from app.db import session
    cli = _cli()
    db = DB(SimpleNamespace(id=11))
    code = "S" * 43
    destination = tmp_path / "ticket.json"
    monkeypatch.setattr(config, "settings", SimpleNamespace(db_dialect="mysql"))
    monkeypatch.setattr(session, "db_enabled", lambda: True)
    monkeypatch.setattr(session, "get_sessionmaker", lambda: lambda: db)
    monkeypatch.setattr(cli, "_hidden_token", lambda: "applicant-wx-token")
    from app.services import wx_auth_service
    monkeypatch.setattr(wx_auth_service, "openid_from_bind_token", lambda token: "verified-openid")
    monkeypatch.setattr(cli, "_operator", lambda: "os:tester")
    # The CLI's tenant lookup is deliberately read-only; issue_in_session owns
    # the account lock (covered by issuer and MySQL tests).
    db.scalars = lambda statement: SimpleNamespace(one_or_none=lambda: SimpleNamespace(id=11))
    def issue_code(*a, **kw):
        assert destination.read_text() == ""
        if failure == "audit":
            raise RuntimeError("injected audit failure")
        return {"bindingApprovalToken": code, "approvalRef": "wxap-test", "expiresIn": 300}
    monkeypatch.setattr(approval, "issue_in_session", issue_code)
    def commit():
        assert destination.read_text() == ""
        db.calls.append("commit")
        if failure == "commit":
            raise RuntimeError("lost commit acknowledgement")
    db.commit = commit
    result = cli.main(["--tenant-code", "school", "--user-id", "7", "--expected-version", "3",
                       "--incident-ref", "TICKET-265", "--ticket-file", str(destination),
                       "--apply", "--identity-verified"])
    output = capsys.readouterr()
    assert code not in output.out + output.err
    assert "applicant-wx-token" not in output.out + output.err
    if failure is None:
        assert result == 0 and json.loads(destination.read_text())["bindingApprovalToken"] == code
        assert destination.stat().st_mode & 0o777 == 0o600
    else:
        assert result == 1 and destination.read_text() == ""
        receipt = json.loads(output.err)
        assert receipt["outcome"] == ("UNCONFIRMED" if failure == "commit" else "NOT_COMMITTED")
        assert receipt["replayApproval"] is False


def test_cli_never_overwrites_existing_ticket(monkeypatch, tmp_path, capsys):
    cli = _cli()
    destination = tmp_path / "ticket.json"
    destination.write_text("existing private data")
    monkeypatch.setattr(cli, "_hidden_token", lambda: pytest.fail("must reject before requesting any token"))
    assert cli.main(["--tenant-code", "school", "--user-id", "7", "--expected-version", "3",
                     "--incident-ref", "TICKET-265", "--ticket-file", str(destination),
                     "--apply", "--identity-verified"]) == 1
    assert destination.read_text() == "existing private data"
    assert json.loads(capsys.readouterr().err)["outcome"] == "NOT_COMMITTED"


@pytest.mark.parametrize("kind", ["PLATFORM_OP", "PLATFORM_SUPER_ADMIN"])
def test_school_wechat_token_issuer_rejects_platform_before_any_grant(monkeypatch, kind):
    monkeypatch.setattr(auth, "_ensure_tenant_login_allowed", lambda *a: pytest.fail("school issuer must reject first"))
    with pytest.raises(AppException) as exc:
        p0.build_login_result(DB(), user(user_type=kind), client_type="MP")
    assert exc.value.code == "NO_PERMISSION"
