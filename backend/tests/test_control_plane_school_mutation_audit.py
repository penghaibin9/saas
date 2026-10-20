"""School mutation audit registration and same-transaction rollback contracts."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.context import get_tenant, set_tenant
from app.db.session import get_sessionmaker

TENANT_ID = 1000000000000096541
ACTIONS = (
    "USER_DISABLE", "USER_ENABLE", "USER_UNLOCK", "ROLE_DISABLE", "ROLE_ENABLE",
    "BRAND_CONFIG", "BRAND_CONFIG_RESET",
)


def test_school_mutation_actions_reach_the_actual_critical_writer():
    from app.services import audit_log, audit_log_legacy

    # The facade's set alone is not enough: the delegated function reads legacy globals.
    assert set(ACTIONS) <= audit_log.CRITICAL_ACTIONS
    assert audit_log.CRITICAL_ACTIONS is audit_log_legacy.CRITICAL_ACTIONS
    assert set(ACTIONS) <= audit_log.record_critical_in_session.__globals__["CRITICAL_ACTIONS"]
    with pytest.raises(ValueError, match="CRITICAL_ACTIONS"):
        audit_log.record_critical_in_session(None, "UNREGISTERED_TEST_ACTION", "test")


@pytest.fixture
def school_case(db_mode):
    from app.models import Role, Tenant, TenantBrandConfig, User

    prior = get_tenant()
    with get_sessionmaker()() as db:
        db.add(Tenant(id=TENANT_ID, tenant_code="school-audit-contract",
                      school_name="学校同事务审计验收", status="ACTIVE"))
        account = User(tenant_id=TENANT_ID, login_name="audit-target", real_name="审计测试账号",
                       password_hash="not-a-login-credential", user_type="TEACHER",
                       status="ACTIVE", version=1)
        role = Role(tenant_id=TENANT_ID, role_code="AUDIT_CUSTOM", role_name="审计测试角色",
                    role_type="CUSTOM", status="ACTIVE", version=1)
        brand = TenantBrandConfig(tenant_id=TENANT_ID, primary_color="#123456",
                                  watermark_text="修改前水印", version=1)
        db.add_all([account, role, brand])
        db.commit()
        ids = {"user": int(account.id), "role": int(role.id), "brand": int(brand.id)}
    set_tenant({"tenantId": str(TENANT_ID)})
    try:
        yield ids
    finally:
        set_tenant(prior)


def _prepare(case: dict, action: str) -> None:
    from app.models import Role, User

    with get_sessionmaker()() as db:
        account = db.scalar(select(User).where(User.tenant_id == TENANT_ID, User.id == case["user"]))
        account.status = {"USER_ENABLE": "DISABLED", "USER_UNLOCK": "LOCKED"}.get(action, "ACTIVE")
        role = db.scalar(select(Role).where(Role.tenant_id == TENANT_ID, Role.id == case["role"]))
        role.status = "DISABLED" if action == "ROLE_ENABLE" else "ACTIVE"
        db.commit()


def _snapshot(case: dict) -> tuple:
    from app.models import Role, TenantBrandConfig, User

    with get_sessionmaker()() as db:
        account = db.scalar(select(User).where(User.tenant_id == TENANT_ID, User.id == case["user"]))
        role = db.scalar(select(Role).where(Role.tenant_id == TENANT_ID, Role.id == case["role"]))
        brand = db.scalar(select(TenantBrandConfig).where(TenantBrandConfig.tenant_id == TENANT_ID))
        return (account.status, account.version, role.status, role.version,
                brand.primary_color, brand.watermark_text, brand.version, dict(brand.config_json or {}))


def _invoke(case: dict, action: str) -> dict:
    from app.services import system_mutation_receipt_service as mutation
    from app.services import tenant_brand_authority_service as brand

    kwargs = {"expected_version": 1, "reason": "学校动作同事务审计验收"}
    if action.startswith("USER_"):
        return mutation.set_user_status(case["user"], action=action.removeprefix("USER_"), **kwargs)
    if action.startswith("ROLE_"):
        return mutation.set_role_status(case["role"], action=action.removeprefix("ROLE_"), **kwargs)
    if action == "BRAND_CONFIG":
        return brand.update_school_brand(TENANT_ID, brand={"watermarkText": "修改后水印"}, **kwargs)
    return brand.reset_school_brand(TENANT_ID, **kwargs)


def _audits(action: str) -> list:
    from app.models import SecurityAuditLog

    with get_sessionmaker()() as db:
        return list(db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == TENANT_ID, SecurityAuditLog.action == action,
        )).all())


@pytest.mark.parametrize("action", ACTIONS)
def test_mutation_and_exact_audit_commit_together(school_case, action, monkeypatch):
    from app.services import auth_service_db

    _prepare(school_case, action)
    monkeypatch.setattr(auth_service_db, "invalidate_subject_cache", lambda *_a, **_k: 0)
    monkeypatch.setattr(auth_service_db, "invalidate_tenant_subject_caches", lambda *_a, **_k: 0)
    out = _invoke(school_case, action)
    assert out["version"] == 2
    rows = _audits(action)
    assert len(rows) == 1
    key = "user" if action.startswith("USER_") else "role" if action.startswith("ROLE_") else "brand"
    assert rows[0].resource_id == str(school_case[key])
    assert rows[0].result == "SUCCESS"
    state = _snapshot(school_case)
    if key == "user":
        assert state[:2] == ("DISABLED" if action == "USER_DISABLE" else "ACTIVE", 2)
    elif key == "role":
        assert state[2:4] == ("DISABLED" if action == "ROLE_DISABLE" else "ACTIVE", 2)
    elif action == "BRAND_CONFIG":
        assert state[5:7] == ("修改后水印", 2)
    else:
        assert state[4:7] == ("#2563EB", "", 2)


@pytest.mark.parametrize("action", ACTIONS)
def test_audit_failure_rolls_back_business_and_version(school_case, action, monkeypatch):
    from app.services import audit_log, auth_service_db, db_service

    _prepare(school_case, action)
    before = _snapshot(school_case)
    cache_calls = []
    monkeypatch.setattr(auth_service_db, "invalidate_subject_cache", lambda *_a, **_k: cache_calls.append("user"))
    monkeypatch.setattr(auth_service_db, "invalidate_tenant_subject_caches", lambda *_a, **_k: cache_calls.append("tenant"))
    original = db_service.audit_insert_in_session

    def fail_after_flush(db, actual_action, *args, **kwargs):
        assert actual_action == action
        original(db, actual_action, *args, **kwargs)
        db.flush()  # Exercise rollback after both business and audit reached the real MySQL transaction.
        raise RuntimeError("injected audit persistence failure")

    monkeypatch.setattr(db_service, "audit_insert_in_session", fail_after_flush)
    with pytest.raises(audit_log.AuditPersistenceError):
        _invoke(school_case, action)
    assert _snapshot(school_case) == before
    assert _audits(action) == []
    assert cache_calls == [], "An uncommitted mutation must not run post-commit recovery"
