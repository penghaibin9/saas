"""System-management post-commit/cache separation regression locks."""
from __future__ import annotations

import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException


TENANT = 1000000000000096501
ACTOR = {"userId": "db-990001", "realName": "系统治理测试管理员", "currentRoleCode": "SCHOOL_ADMIN"}


def _db():
    from app.db.session import get_sessionmaker
    return get_sessionmaker()()


def _ensure_tenant() -> None:
    from app.models import Tenant

    db = _db()
    try:
        row = db.get(Tenant, TENANT)
        if row is None:
            db.add(Tenant(
                id=TENANT,
                tenant_code="system-mutation-receipt",
                school_name="系统变更回执测试学校",
                status="ACTIVE",
            ))
            db.commit()
    finally:
        db.close()


def _user(login: str, *, status: str = "ACTIVE") -> int:
    from app.core.security import hash_password
    from app.models import User

    db = _db()
    try:
        row = db.query(User).filter(
            User.tenant_id == TENANT,
            User.login_name == login,
        ).first()
        if row is None:
            row = User(
                tenant_id=TENANT,
                login_name=login,
                real_name=f"测试账号-{login}",
                password_hash=hash_password("Before@2026"),
                user_type="TEACHER",
                status=status,
                must_change_password=False,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        else:
            row.status = status
            row.must_change_password = False
            row.version = int(row.version or 0) + 1
            db.commit()
        return int(row.id)
    finally:
        db.close()


def _role(code: str, *, status: str = "ACTIVE") -> int:
    from app.models import Role

    db = _db()
    try:
        row = db.query(Role).filter(
            Role.tenant_id == TENANT,
            Role.role_code == code,
        ).first()
        if row is None:
            row = Role(
                tenant_id=TENANT,
                role_code=code,
                role_name=f"测试角色-{code}",
                role_type="CUSTOM",
                status=status,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        else:
            row.status = status
            row.version = int(row.version or 0) + 1
            db.commit()
        return int(row.id)
    finally:
        db.close()


def _user_state(user_id: int) -> tuple[str, int, str, bool]:
    from app.models import User

    db = _db()
    try:
        row = db.get(User, user_id)
        return str(row.status), int(row.version or 0), str(row.password_hash or ""), bool(row.must_change_password)
    finally:
        db.close()


def _role_state(role_id: int) -> tuple[str, int]:
    from app.models import Role

    db = _db()
    try:
        row = db.get(Role, role_id)
        return str(row.status), int(row.version or 0)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _tenant_ctx(db_mode):
    _ensure_tenant()
    set_tenant({"tenantId": str(TENANT)})
    try:
        yield
    finally:
        set_tenant(None)


def test_user_status_commit_survives_cache_failure_and_reports_recovery(monkeypatch):
    from app.services import system_mutation_receipt_service as svc

    uid = _user("receipt-status")
    before = _user_state(uid)

    def _cache_down(*_a, **_k):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr("app.services.auth_service_db.invalidate_subject_cache", _cache_down)
    out = svc.set_user_status(
        uid, action="DISABLE", reason="离职交接测试停用",
        expected_version=before[1], user=ACTOR,
    )
    after = _user_state(uid)

    assert after[0] == "DISABLED"
    assert after[1] == before[1] + 1
    assert out["runtimeMaterialized"] is True
    assert out["cacheInvalidated"] is False
    assert out["cacheRecoveryRequired"] is True
    assert "不要重放业务操作" in out["warning"]
    assert out["optimisticLockEnforced"] is True


def test_idempotent_user_retry_is_cache_only_recovery(monkeypatch):
    from app.services import system_mutation_receipt_service as svc

    uid = _user("receipt-idempotent", status="DISABLED")
    before = _user_state(uid)
    calls = []
    monkeypatch.setattr(
        "app.services.auth_service_db.invalidate_subject_cache",
        lambda subject, tenant_id: calls.append((subject, tenant_id)) or 1,
    )
    out = svc.set_user_status(uid, action="DISABLE", reason="重复停用用于缓存恢复", user=ACTOR)
    after = _user_state(uid)

    assert out["idempotent"] is True
    assert out["cacheInvalidated"] is True
    assert after[1] == before[1], "幂等缓存恢复不得重放业务版本"
    assert calls == [(f"db-{uid}", TENANT)]


def test_unlock_is_a_real_backend_action(monkeypatch):
    from app.services import system_mutation_receipt_service as svc

    uid = _user("receipt-locked", status="LOCKED")
    version = _user_state(uid)[1]
    monkeypatch.setattr("app.services.auth_service_db.invalidate_subject_cache", lambda *_a, **_k: 1)
    out = svc.set_user_status(uid, action="UNLOCK", expected_version=version, user=ACTOR)
    assert out["status"] == "ACTIVE"
    assert _user_state(uid)[0] == "ACTIVE"


def test_reset_password_returns_one_time_secret_even_when_cache_fails(monkeypatch):
    from app.services import system_mutation_receipt_service as svc

    uid = _user("receipt-password")
    before = _user_state(uid)

    def _cache_down(*_a, **_k):
        raise RuntimeError("redis unavailable after commit")

    monkeypatch.setattr("app.services.auth_service_db.invalidate_subject_cache", _cache_down)
    out = svc.reset_user_password(uid, expected_version=before[1], user=ACTOR)
    after = _user_state(uid)

    assert out["tempPassword"].startswith("Tmp")
    assert after[2] != before[2]
    assert after[3] is True
    assert after[1] == before[1] + 1
    assert out["runtimeMaterialized"] is True
    assert out["cacheInvalidated"] is False
    assert out["cacheRecoveryRequired"] is True


def test_stale_account_version_is_rejected_before_password_mutation(monkeypatch):
    from app.services import system_mutation_receipt_service as svc

    uid = _user("receipt-stale")
    before = _user_state(uid)
    monkeypatch.setattr("app.services.auth_service_db.invalidate_subject_cache", lambda *_a, **_k: 1)
    with pytest.raises(AppException) as caught:
        svc.reset_user_password(uid, expected_version=before[1] - 1, user=ACTOR)
    assert caught.value.code == "DATA_CONFLICT"
    assert _user_state(uid)[2] == before[2]


def test_role_status_commit_survives_tenant_cache_failure(monkeypatch):
    from app.services import system_mutation_receipt_service as svc

    rid = _role("RECEIPT_ROLE")
    before = _role_state(rid)

    def _cache_down(*_a, **_k):
        raise RuntimeError("redis tenant pattern failed")

    monkeypatch.setattr("app.services.auth_service_db.invalidate_tenant_subject_caches", _cache_down)
    out = svc.set_role_status(
        rid, action="DISABLE", reason="岗位角色阶段性停用",
        expected_version=before[1], user=ACTOR,
    )
    after = _role_state(rid)

    assert after == ("DISABLED", before[1] + 1)
    assert out["runtimeMaterialized"] is True
    assert out["cacheInvalidated"] is False
    assert out["cacheRecoveryRequired"] is True


def test_subject_cache_recovery_never_changes_user_version(monkeypatch):
    from app.services import system_mutation_receipt_service as svc

    uid = _user("receipt-recover")
    before = _user_state(uid)
    monkeypatch.setattr("app.services.auth_service_db.invalidate_subject_cache", lambda *_a, **_k: 2)
    out = svc.recover_subject_cache(uid)
    after = _user_state(uid)

    assert out["cacheInvalidated"] is True
    assert out["cacheRecoveryRequired"] is False
    assert out["removedKeys"] == 2
    assert after[1] == before[1]
