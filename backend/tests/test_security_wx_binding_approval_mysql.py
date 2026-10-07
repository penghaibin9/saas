"""Native MySQL/API approval tests; db_mode guarantees an isolated test schema."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.exceptions import AppException

TID = 1000000000000000001
UID = 8265001
PASSWORD = "Independent-binding-test-only!"
OPENID = "pr265-independent-wechat-test"


@pytest.fixture
def school_account(db_mode):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, User, UserRole
    with get_sessionmaker()() as db:
        account = User(id=UID, tenant_id=TID, login_name="pr265-binding-student",
                       real_name="绑定验收账号", user_type="STUDENT", status="ACTIVE",
                       password_hash=hash_password(PASSWORD), version=3)
        role = Role(tenant_id=TID, role_code="STUDENT", role_name="学生", role_type="SYSTEM", status="ACTIVE")
        db.add(account)
        # Reuse any existing published school role; no runtime name-based grant.
        existing = db.scalars(select(Role).where(Role.tenant_id == TID, Role.role_code == "STUDENT")).first()
        if existing is None:
            db.add(role)
            db.flush()
        else:
            role = existing
        db.add(UserRole(tenant_id=TID, user_id=UID, role_id=role.id, status="ACTIVE"))
        db.commit()
    return UID


def _issue(openid=OPENID):
    from app.db.session import get_sessionmaker
    from app.services.wx_binding_approval_service import issue_in_session
    with get_sessionmaker()() as db:
        ticket = issue_in_session(db, tenant_id=TID, user_id=UID, expected_version=3,
                                  openid=openid, incident_ref="PR265-INDEPENDENT-CHECK",
                                  operator="os:pytest", identity_verified=True)
        db.commit()
    return ticket


def _strict(monkeypatch):
    from app.services import wx_binding_approval_service as service
    # Only the approval policy is forced strict. Application-wide test flags,
    # database, password verification, roles, and critical audit stay real.
    monkeypatch.setattr(service, "settings", SimpleNamespace(APP_ENV="production", is_prod=True, mock_login_enabled=False))


def _wx_token():
    from app.services.wx_auth_service import _temporary_wx_token
    return _temporary_wx_token(OPENID, "wx_bind")


def _invoke(ticket=None):
    from app.services.control_plane_auth_service import wx_bind
    return wx_bind(_wx_token(), "pr265-binding-student", PASSWORD, "demo",
                   binding_approval_token=(ticket or {}).get("bindingApprovalToken"))


def _row(db, ticket):
    from app.models.auth_risk import AuthChallengeState
    from app.services.wx_binding_approval_service import _token_hash
    return db.scalars(select(AuthChallengeState).where(
        AuthChallengeState.challenge_id_hash == _token_hash(ticket["bindingApprovalToken"]),
    )).one()


def test_mysql_password_only_cannot_create_binding(school_account, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import User, WxAccountBinding
    _strict(monkeypatch)
    with pytest.raises(AppException) as exc:
        _invoke()
    assert exc.value.code == "WX_BIND_APPROVAL_REQUIRED"
    with get_sessionmaker()() as db:
        assert db.get(User, UID).wx_openid is None
        assert db.scalars(select(WxAccountBinding).where(WxAccountBinding.user_id == UID)).first() is None


def test_mysql_real_route_delivers_code_and_existing_login_stays_usable(client, school_account, monkeypatch):
    from app.api.v1.router import api_router
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog, User, WxAccountBinding
    from app.services import wx_auth_service
    _strict(monkeypatch)
    handlers = [r for r in api_router.routes if getattr(r, "path", None) == "/auth/wx-bind" and "POST" in r.methods]
    assert len(handlers) == 1 and handlers[0].endpoint.__module__ == "app.api.v1.control_plane_auth"
    ticket = _issue()
    response = client.post("/api/v1/auth/wx-bind", json={
        "wxToken": _wx_token(), "loginName": "pr265-binding-student", "password": PASSWORD,
        "tenantCode": "demo", "clientType": "STUDENT_MINI", **{"bindingApprovalToken": ticket["bindingApprovalToken"]},
    })
    assert response.status_code == 200, response.text
    assert response.json()["data"]["accessToken"]
    with get_sessionmaker()() as db:
        assert _row(db, ticket).consumed_at is not None
        account = db.get(User, UID)
        assert account.wx_openid == OPENID
        assert db.scalars(select(WxAccountBinding).where(WxAccountBinding.user_id == UID)).one().status == "ACTIVE"
        audits = db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == TID,
            SecurityAuditLog.action.in_(("WX_BIND_APPROVAL_AUTHORIZED", "WX_BINDING_ACTIVATED")),
        )).all()
        assert {a.action for a in audits} == {"WX_BIND_APPROVAL_AUTHORIZED", "WX_BINDING_ACTIVATED"}
        assert all(ticket["bindingApprovalToken"] not in str(a.detail_json) for a in audits)
    # The only mocked dependency is the external WeChat server; existing login
    # is resolved through the real binding table and installed token issuer.
    monkeypatch.setattr(wx_auth_service, "code2session", lambda code: OPENID)
    assert wx_auth_service.wx_login("weixin-test-code")["userId"] == f"db-{UID}"


def test_mysql_binding_audit_failure_rolls_back_consumption_and_allows_safe_retry(school_account, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import User, WxAccountBinding
    from app.services import audit_log
    _strict(monkeypatch)
    ticket = _issue()
    real_audit = audit_log.record_critical_in_session
    def fail_binding(db, action, *a, **kw):
        if action == "WX_BINDING_ACTIVATED":
            raise RuntimeError("injected-audit-failure")
        return real_audit(db, action, *a, **kw)
    monkeypatch.setattr(audit_log, "record_critical_in_session", fail_binding)
    with pytest.raises(RuntimeError, match="injected-audit-failure"):
        _invoke(ticket)
    with get_sessionmaker()() as db:
        assert _row(db, ticket).consumed_at is None
        assert db.get(User, UID).wx_openid is None
        assert db.scalars(select(WxAccountBinding).where(WxAccountBinding.user_id == UID)).first() is None
    monkeypatch.setattr(audit_log, "record_critical_in_session", real_audit)
    assert _invoke(ticket)["userId"] == f"db-{UID}"


@pytest.mark.parametrize("field,value", [("tenant_id", 999999), ("id", UID + 1), ("version", 4)])
def test_mysql_foreign_or_changed_subject_cannot_consume(school_account, monkeypatch, field, value):
    from app.db.session import get_sessionmaker
    from app.services.wx_binding_approval_service import consume_in_session
    _strict(monkeypatch)
    ticket = _issue()
    subject = dict(tenant_id=TID, id=UID, version=3, user_type="STUDENT", status="ACTIVE", is_deleted=False)
    subject[field] = value
    with get_sessionmaker()() as db:
        with pytest.raises(AppException):
            consume_in_session(db, SimpleNamespace(**subject), OPENID, ticket["bindingApprovalToken"])
        db.rollback()
    with get_sessionmaker()() as db:
        assert _row(db, ticket).consumed_at is None


def test_mysql_two_connections_only_one_committed_consumer(school_account, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.services.wx_binding_approval_service import consume_in_session
    _strict(monkeypatch)
    ticket = _issue()
    barrier = Barrier(2)
    def consume(_):
        subject = SimpleNamespace(tenant_id=TID, id=UID, version=3, user_type="STUDENT", status="ACTIVE", is_deleted=False)
        with get_sessionmaker()() as db:
            barrier.wait(timeout=10)
            try:
                ref = consume_in_session(db, subject, OPENID, ticket["bindingApprovalToken"])
                db.commit()
                return ref
            except AppException as exc:
                db.rollback()
                assert exc.code == "WX_BIND_APPROVAL_INVALID"
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, range(2), timeout=30))
    assert results.count(ticket["approvalRef"]) == 1 and results.count(None) == 1


def test_mysql_expiry_and_account_version_change_invalidate_approval(school_account, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import User
    _strict(monkeypatch)
    ticket = _issue()
    with get_sessionmaker()() as db:
        db.get(User, UID).version = 4
        db.commit()
    with pytest.raises(AppException) as exc:
        _invoke(ticket)
    assert exc.value.code == "WX_BIND_APPROVAL_INVALID"
    with get_sessionmaker()() as db:
        assert _row(db, ticket).consumed_at is None
        db.get(User, UID).version = 3
        _row(db, ticket).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    with pytest.raises(AppException) as exc:
        _invoke(ticket)
    assert exc.value.code == "WX_BIND_APPROVAL_INVALID"
