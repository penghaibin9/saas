from datetime import datetime, timedelta
import time

import pytest

from app.core.exceptions import AppException
from app.models.customer_success import SupportTicket
from app.services import platform_access_governance_service as pam

TID = 1000000000000000001


def _actor(user_id: int = 81001, *, mfa: bool = True, age_seconds: int = 0) -> dict:
    return {
        "userId": str(user_id),
        "currentRoleCode": "PLATFORM_OPERATIONS",
        "userType": "PLATFORM_OPERATIONS",
        "authTime": int(time.time()) - int(age_seconds),
        "amr": ["pwd", "mfa"] if mfa else ["pwd"],
        "acr": "urn:mfa" if mfa else "urn:pwd",
    }


def _ticket(db, *, tenant_id: int = TID, assignee_user_id: int | None = 81001, status: str = "OPEN") -> SupportTicket:
    row = SupportTicket(
        tenant_id=tenant_id,
        title=f"PAM Gold {time.time_ns()}",
        description="受控协助生产门禁",
        severity="P1",
        status=status,
        reporter_name="control-plane-test",
        assignee_user_id=assignee_user_id,
        assignee_name="平台主管",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _session(ticket: SupportTicket, *, operator: int = 81001, tenant_id: int = TID, scope: str = "tenant.context.read") -> dict:
    now = datetime.utcnow()
    return {
        "operatorUserId": str(operator),
        "tenantId": tenant_id,
        "status": "ACTIVE",
        "ticketId": str(ticket.id),
        "scopes": [scope],
        "startedAt": (now - timedelta(minutes=1)).isoformat(),
        "expiresAt": (now + timedelta(minutes=10)).isoformat(),
    }


def test_pam_elevation_requires_recent_mfa_before_any_storage(monkeypatch):
    called = {"existing": False}

    def should_not_read(*args, **kwargs):
        called["existing"] = True
        raise AssertionError("storage must not be touched before MFA assurance")

    monkeypatch.setattr(pam._canonical, "_existing", should_not_read)
    payload = {
        "requestId": "pam-elev-no-mfa-0001",
        "userId": "81002",
        "capabilities": ["operations.manage"],
        "durationMinutes": 30,
        "reason": "生产事件临时提权",
    }
    with pytest.raises(AppException) as exc:
        pam.create_elevation(payload, actor=_actor(mfa=False))
    assert exc.value.code == "PLATFORM_MFA_ASSURANCE_REQUIRED"
    assert called["existing"] is False


def test_pam_elevation_rejects_stale_auth_even_with_mfa(monkeypatch):
    monkeypatch.setattr(pam._canonical, "_existing", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must fail before storage")))
    payload = {
        "requestId": "pam-elev-stale-0001",
        "userId": "81002",
        "capabilities": ["operations.manage"],
        "durationMinutes": 30,
        "reason": "生产事件临时提权",
    }
    with pytest.raises(AppException) as exc:
        pam.create_elevation(payload, actor=_actor(mfa=True, age_seconds=601))
    assert exc.value.code == "PLATFORM_RECENT_AUTH_REQUIRED"


def test_support_runtime_revalidates_live_ticket_and_assignee(db_mode):
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        ticket = _ticket(db)
        session = _session(ticket)
        actor = _actor()
        assert pam.support_session_allows(session, user=actor, tenant_id=TID, scope="tenant.context.read") is True

        # Reassignment revokes access immediately; session status/TTL alone cannot keep it alive.
        ticket.assignee_user_id = 81099
        ticket.version = int(ticket.version or 0) + 1
        db.commit()
        assert pam.support_session_allows(session, user=actor, tenant_id=TID, scope="tenant.context.read") is False

        # Restore assignee then close ticket: runtime access still stays denied immediately.
        ticket.assignee_user_id = 81001
        ticket.status = "CLOSED"
        ticket.version = int(ticket.version or 0) + 1
        db.commit()
        assert pam.support_session_allows(session, user=actor, tenant_id=TID, scope="tenant.context.read") is False
    finally:
        db.close()


def test_support_runtime_denies_cross_tenant_scope_expiry_and_operator(db_mode):
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        ticket = _ticket(db)
        session = _session(ticket)
        actor = _actor()
        assert pam.support_session_allows(session, user=actor, tenant_id=TID + 1, scope="tenant.context.read") is False
        assert pam.support_session_allows(session, user=actor, tenant_id=TID, scope="tenant.audit.read") is False
        assert pam.support_session_allows(session, user=_actor(81002), tenant_id=TID, scope="tenant.context.read") is False
        assert pam.support_session_allows({**session, "expiresAt": (datetime.utcnow() - timedelta(seconds=1)).isoformat()}, user=actor, tenant_id=TID, scope="tenant.context.read") is False
        assert pam.support_session_allows({**session, "status": "TERMINATED"}, user=actor, tenant_id=TID, scope="tenant.context.read") is False
        assert pam.support_session_allows({**session, "scopes": ["*"]}, user=actor, tenant_id=TID, scope="tenant.context.read") is False
    finally:
        db.close()


def test_support_ticket_validation_hides_cross_tenant_existence(db_mode):
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        ticket = _ticket(db, tenant_id=TID)
        with pytest.raises(AppException) as exc:
            pam._canonical._validate_support_ticket(TID + 1, ticket.id, user=_actor())
        assert exc.value.code == "SUPPORT_TICKET_NOT_AVAILABLE"
        assert exc.value.http_status == 404
    finally:
        db.close()


def test_platform_access_view_uses_stable_request_ids_and_real_scope_catalog():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    source = (root / "frontend/src/modules/platform/views/control/PlatformAccessView.vue").read_text(encoding="utf-8")
    assert "randomUUID" in source
    assert "requestId: requestId()" in source
    assert "SupportTicket 数字 ID" in source
    assert "tenant.context.read" in source
    assert "tenant.audit.read" in source
    assert "file.metadata.read" in source
    assert "file.metadata," not in source
    assert "tenant.health" not in source
