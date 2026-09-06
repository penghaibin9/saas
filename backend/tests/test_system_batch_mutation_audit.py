"""Batch account status changes and summary evidence share one MySQL transaction."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.context import get_tenant, set_tenant
from app.db.session import get_sessionmaker

TENANT_ID = 1000000000000096551
BATCH_ACTIONS = ("USER_BATCH_DISABLE", "USER_BATCH_ENABLE")


def test_batch_actions_are_registered_in_the_actual_audit_writer():
    from app.services import audit_log, audit_log_legacy

    assert set(BATCH_ACTIONS) <= audit_log.CRITICAL_ACTIONS
    assert audit_log.CRITICAL_ACTIONS is audit_log_legacy.CRITICAL_ACTIONS
    assert set(BATCH_ACTIONS) <= audit_log.record_critical_in_session.__globals__["CRITICAL_ACTIONS"]
    with pytest.raises(ValueError, match="CRITICAL_ACTIONS"):
        audit_log.record_critical_in_session(None, "UNKNOWN_BATCH_ACTION", "test")


@pytest.fixture
def batch_accounts_case(db_mode):
    from app.models import Tenant, User

    prior = get_tenant()
    with get_sessionmaker()() as db:
        db.add(Tenant(id=TENANT_ID, tenant_code="batch-audit-contract",
                      school_name="批量账号审计验收", status="ACTIVE"))
        accounts = [User(tenant_id=TENANT_ID, login_name=f"batch-audit-{i}",
                         real_name=f"批量审计账号{i}", password_hash="not-a-login-credential",
                         user_type="TEACHER", status="ACTIVE", version=1) for i in range(2)]
        db.add_all(accounts)
        db.commit()
        ids = [int(account.id) for account in accounts]
    set_tenant({"tenantId": str(TENANT_ID)})
    try:
        yield ids
    finally:
        set_tenant(prior)


def _prepare(ids, action):
    from app.models import User

    with get_sessionmaker()() as db:
        for account in db.scalars(select(User).where(User.tenant_id == TENANT_ID, User.id.in_(ids))):
            account.status = "DISABLED" if action == "ENABLE" else "ACTIVE"
        db.commit()


def _state(ids):
    from app.models import User

    with get_sessionmaker()() as db:
        return list(db.execute(select(User.id, User.status, User.version).where(
            User.tenant_id == TENANT_ID, User.id.in_(ids),
        ).order_by(User.id)).all())


def _audit_count(action):
    from app.models import SecurityAuditLog

    with get_sessionmaker()() as db:
        return len(list(db.scalars(select(SecurityAuditLog.id).where(
            SecurityAuditLog.tenant_id == TENANT_ID,
            SecurityAuditLog.action == f"USER_BATCH_{action}",
        ))))


@pytest.mark.parametrize("action", ["DISABLE", "ENABLE"])
def test_batch_commits_both_accounts_and_exact_summary_audit(batch_accounts_case, action, monkeypatch):
    from app.services import auth_service_db, system_mutation_receipt_service as mutation

    ids = batch_accounts_case
    _prepare(ids, action)
    monkeypatch.setattr(auth_service_db, "invalidate_tenant_subject_caches", lambda *_a, **_k: 0)
    result = mutation.batch_accounts(ids, action=action, reason="批量账号同事务验收")
    assert result["runtimeMaterialized"] is True
    assert result["cacheInvalidated"] is True
    assert result["cacheRecoveryRequired"] is False
    assert [(row.status, row.version) for row in _state(ids)] == [
        ("DISABLED" if action == "DISABLE" else "ACTIVE", 2),
    ] * 2
    assert _audit_count(action) == 1


@pytest.mark.parametrize("action", ["DISABLE", "ENABLE"])
def test_batch_audit_failure_rolls_back_all_accounts_and_versions(batch_accounts_case, action, monkeypatch):
    from app.services import audit_log, auth_service_db, db_service, system_mutation_receipt_service as mutation

    ids = batch_accounts_case
    _prepare(ids, action)
    before = _state(ids)
    cache_calls = []
    monkeypatch.setattr(auth_service_db, "invalidate_tenant_subject_caches",
                        lambda *_a, **_k: cache_calls.append("tenant"))
    original = db_service.audit_insert_in_session

    def fail_after_flush(db, actual_action, *args, **kwargs):
        assert actual_action == f"USER_BATCH_{action}"
        original(db, actual_action, *args, **kwargs)
        db.flush()
        raise RuntimeError("injected batch audit failure")

    monkeypatch.setattr(db_service, "audit_insert_in_session", fail_after_flush)
    with pytest.raises(audit_log.AuditPersistenceError):
        mutation.batch_accounts(ids, action=action, reason="批量失败回滚验收")
    assert _state(ids) == before
    assert _audit_count(action) == 0
    assert cache_calls == []
