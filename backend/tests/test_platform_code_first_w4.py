from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.core.security import create_access_token


def _ensure_tenant(tenant_id: int) -> None:
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        row = db.get(Tenant, tenant_id)
        if row is None:
            db.add(Tenant(id=tenant_id, tenant_code=f"w4-{tenant_id}", school_name="W4并发学校", status="ACTIVE"))
            db.commit()
    finally:
        db.close()


def _owner_headers() -> dict[str, str]:
    token = create_access_token({
        "userId": "w4-owner",
        "realName": "W4平台主管",
        "userType": "PLATFORM_SUPER_ADMIN",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "tenantId": "0",
        "tid": "platform",
        "activeContextId": "ctx-w4",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def test_w4_rules_expected_version_prevents_lost_update(db_mode):
    from app.services import platform_control_authority_service as authority

    tenant_id = 1000000000000096401
    _ensure_tenant(tenant_id)
    initial = authority.rules_projection(tenant_id)
    version = int(initial["overrideVersion"])

    first = authority.update_rules(
        tenant_id,
        rules={"departure": {"disciplineBlocks": True}},
        expected_version=version,
        reason="W4第一次规则修改",
    )
    assert int(first["overrideVersion"]) == version + 1

    with pytest.raises(AppException) as caught:
        authority.update_rules(
            tenant_id,
            rules={"departure": {"disciplineBlocks": False}},
            expected_version=version,
            reason="W4过期版本规则修改",
        )
    assert caught.value.code == "DATA_CONFLICT"


def test_w4_tenant_brand_expected_version_prevents_lost_update(db_mode):
    from app.services import tenant_brand_authority_service as brand_authority

    tenant_id = 1000000000000096402
    _ensure_tenant(tenant_id)
    initial = brand_authority.brand_projection(tenant_id)
    version = int(initial["version"])

    first = brand_authority.update_school_brand(
        tenant_id,
        brand={"watermarkText": "W4第一版水印"},
        expected_version=version,
        reason="W4第一次品牌修改",
        user={"userId": "db-1", "realName": "学校管理员"},
    )
    assert int(first["version"]) == version + 1

    with pytest.raises(AppException) as caught:
        brand_authority.update_school_brand(
            tenant_id,
            brand={"watermarkText": "W4过期写入"},
            expected_version=version,
            reason="W4过期版本品牌修改",
            user={"userId": "db-1", "realName": "学校管理员"},
        )
    assert caught.value.code == "DATA_CONFLICT"


def test_w4_platform_brand_writer_is_retired_and_legacy_brand_is_read_only(client, db_mode):
    from app.services import platform_service
    from app.services import tenant_brand_authority_service as brand_authority

    tenant_id = 1000000000000096403
    _ensure_tenant(tenant_id)
    current = brand_authority.brand_projection(tenant_id)
    brand_authority.update_school_brand(
        tenant_id,
        brand={"watermarkText": "学校唯一真值"},
        expected_version=current["version"],
        reason="学校写入唯一品牌真值",
        user={"userId": "db-1", "realName": "学校管理员"},
    )
    # Historical PlatformConfig(BRAND) may still exist for reconciliation, but
    # it cannot replace TenantBrandConfig at runtime.
    platform_service.put_config_json(
        tenant_id, "BRAND", "-", {"watermarkText": "历史平台主管旧值"}
    )
    projection = brand_authority.brand_projection(tenant_id)
    assert projection["authority"] == "TENANT_BRAND_CONFIG"
    assert projection["brand"]["watermarkText"] == "学校唯一真值"
    assert projection["legacyOverride"]["watermarkText"] == "历史平台主管旧值"
    assert projection["legacyOverrideReadOnly"] is True
    assert projection["repairRequired"] is True

    response = client.put(
        f"/api/v1/platform/tenants/{tenant_id}/brand",
        headers=_owner_headers(),
        json={"brand": {"watermarkText": "平台主管再次覆盖"}, "expectedVersion": 0, "reason": "尝试旧平台写入口"},
    )
    assert response.status_code == 409
    assert response.json()["bizCode"] == "BRAND_AUTHORITY_MOVED"
    assert brand_authority.brand_projection(tenant_id)["brand"]["watermarkText"] == "学校唯一真值"


def test_w4_shared_config_writes_require_reason_and_version(db_mode):
    from app.services import platform_control_authority_service as authority
    from app.services import tenant_brand_authority_service as brand_authority

    tenant_id = 1000000000000096404
    _ensure_tenant(tenant_id)
    with pytest.raises(AppException) as missing_version:
        authority.update_rules(
            tenant_id,
            rules={"departure": {"disciplineBlocks": True}},
            expected_version=None,
            reason="W4缺少版本测试",
        )
    assert missing_version.value.code == "VALIDATION_ERROR"

    with pytest.raises(AppException) as brand_missing_version:
        brand_authority.update_school_brand(
            tenant_id,
            brand={"watermarkText": "x"},
            expected_version=None,
            reason="W4品牌缺少版本",
        )
    assert brand_missing_version.value.code == "VALIDATION_ERROR"

    with pytest.raises(AppException) as reset_missing_version:
        brand_authority.reset_school_brand(
            tenant_id,
            expected_version=None,
            reason="W4恢复品牌缺少版本",
        )
    assert reset_missing_version.value.code == "VALIDATION_ERROR"


def _rule_audits(tenant_id):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog
    with get_sessionmaker()() as db:
        return list(db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == tenant_id,
            SecurityAuditLog.action == "PLATFORM_RULES_UPDATE",
        )).all())


@pytest.mark.parametrize("preexisting", [False, True])
def test_w4_real_concurrent_rule_writes_have_one_winner(db_mode, preexisting):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.db.session import get_engine
    from app.services import platform_control_authority_service as authority

    assert get_engine().dialect.name == "mysql", "This regression requires real MySQL"
    tid = 1000000000000096491
    _ensure_tenant(tid)
    if preexisting:
        authority.update_rules(tid, rules={"student": {"phoneRequired": True}},
                               expected_version=0, reason="建立并发规则基线")
    baseline = authority.rules_projection(tid)
    audit_count = len(_rule_audits(tid))
    start = Barrier(2)
    patches = [{"departure": {"disciplineBlocks": True}}, {"file": {"uploadMaxSizeMb": 31}}]

    def write(index):
        start.wait(timeout=10)
        try:
            out = authority.update_rules(tid, rules=patches[index],
                expected_version=baseline["overrideVersion"], reason=f"并发修改第{index}份规则")
            return (index, "success", out)
        except AppException as exc:
            return (index, exc.code, None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, [0, 1]))
    assert sorted(row[1] for row in results) == ["DATA_CONFLICT", "success"], results
    winner = next(row for row in results if row[1] == "success")
    after = authority.rules_projection(tid)
    assert after["overrideVersion"] == baseline["overrideVersion"] + 1
    assert after == winner[2]
    expected = dict(baseline["override"])
    expected.update(patches[winner[0]])
    assert after["override"] == expected
    assert len(_rule_audits(tid)) == audit_count + 1


@pytest.mark.parametrize("preexisting", [False, True])
def test_w4_audit_failure_rolls_back_rule_payload_version_and_audit(db_mode, monkeypatch, preexisting):
    from app.services import audit_log, db_service
    from app.services import platform_control_authority_service as authority

    tid = 1000000000000096492
    _ensure_tenant(tid)
    if preexisting:
        authority.update_rules(tid, rules={"departure": {"disciplineBlocks": False}},
                               expected_version=0, reason="建立回滚验收基线")
    before = authority.rules_projection(tid)
    audit_count = len(_rule_audits(tid))
    original = db_service.audit_insert_in_session

    def fail_after_insert(db, action, *args, **kwargs):
        assert action == "PLATFORM_RULES_UPDATE"
        original(db, action, *args, **kwargs)
        db.flush()  # Both facts have reached MySQL, but neither may commit.
        raise RuntimeError("injected rule audit persistence failure")

    monkeypatch.setattr(db_service, "audit_insert_in_session", fail_after_insert)
    with pytest.raises(audit_log.AuditPersistenceError):
        authority.update_rules(tid, rules={"departure": {"disciplineBlocks": True}},
            expected_version=before["overrideVersion"], reason="审计故障必须整体回滚")
    assert authority.rules_projection(tid) == before
    assert len(_rule_audits(tid)) == audit_count


@pytest.mark.parametrize("bad_version", [True, False, 1.8, "1.0", "-1", None])
def test_w4_rule_version_never_silently_coerces(db_mode, bad_version):
    from app.services import platform_control_authority_service as authority
    tid = 1000000000000096493
    _ensure_tenant(tid)
    with pytest.raises(AppException) as error:
        authority.update_rules(tid, rules={"departure": {"disciplineBlocks": True}},
                               expected_version=bad_version, reason="拒绝非法版本参数")
    assert error.value.code == "VALIDATION_ERROR"
    assert authority.rules_projection(tid)["override"] == {}


@pytest.mark.parametrize("patch", [{}, {"file": {}}, {"file": {"uploadMaxSizeMb": True}},
                                   {"file": {"allowedFileTypes": ["pdf"]}}])
def test_w4_rule_empty_or_wrong_typed_patch_is_rejected(db_mode, patch):
    from app.services import platform_control_authority_service as authority
    tid = 1000000000000096494
    _ensure_tenant(tid)
    with pytest.raises(AppException) as error:
        authority.update_rules(tid, rules=patch, expected_version=0, reason="类型错误不能保存")
    assert error.value.code == "VALIDATION_ERROR"
    assert len(_rule_audits(tid)) == 0


def test_w4_effective_rules_and_version_use_one_snapshot(monkeypatch):
    from app.services import platform_control_authority_service as authority, platform_service
    monkeypatch.setattr(platform_service, "get_tenant", lambda _tid: {})
    calls = []
    def snapshot(*_args):
        calls.append(True)
        return {"exists": True, "payload": {"file": {"uploadMaxSizeMb": 31}}, "version": 8}
    monkeypatch.setattr(authority, "config_snapshot", snapshot)
    monkeypatch.setattr(platform_service, "effective_rules", lambda *_a: pytest.fail("second snapshot read"))
    out = authority.rules_projection(1000000000000096495)
    assert len(calls) == 1
    assert out["overrideVersion"] == 8
    assert out["rules"]["file"]["uploadMaxSizeMb"] == out["override"]["file"]["uploadMaxSizeMb"] == 31


def test_w4_caller_owned_rule_write_does_not_commit(db_mode):
    from app.db.session import get_sessionmaker
    from app.services import platform_service, platform_control_authority_service as authority
    tid = 1000000000000096496
    _ensure_tenant(tid)
    with get_sessionmaker()() as db:
        platform_service.put_config_json(tid, "RULES", "-", {"file": {"uploadMaxSizeMb": 29}},
                                         expected_version=0, db_session=db)
        db.rollback()
    assert authority.rules_projection(tid)["overrideVersion"] == 0
    assert authority.rules_projection(tid)["override"] == {}
