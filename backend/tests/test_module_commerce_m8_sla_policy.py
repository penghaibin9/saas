from __future__ import annotations

import pytest

from app.core.exceptions import AppException

BASE = 1000000000000046000


def _seed_tenant(tid: int):
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        db.add(Tenant(
            id=tid, tenant_code=f"m8-sla-{tid}", school_name=f"M8SLA-{tid}",
            deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE",
        ))
        db.commit()
    finally:
        db.close()


def _body(expected=0, *, version="SLA-SCHOOL-2026-09"):
    return {
        "expectedVersion": expected,
        "policyVersion": version,
        "targetsHours": {"P0": 1, "P1": 4, "P2": 12, "P3": 36},
        "reason": "学校合同已明确四级售后响应目标",
    }


def test_m8_sla_first_create_requires_explicit_four_targets_and_expected_zero(db_mode):
    from app.services import module_commerce_sla_policy_service as policy

    tid = BASE + 1
    _seed_tenant(tid)
    before = policy.policy_editor(tid)
    assert before["tenantOverride"]["exists"] is False
    assert before["tenantOverride"]["rowVersion"] == 0
    assert before["effective"]["configured"] is False
    assert before["defaultHoursInvented"] is False

    with pytest.raises(AppException) as missing:
        policy.update_tenant_policy({"userId": "91"}, tid, {
            **_body(), "targetsHours": {"P0": 1, "P1": 4, "P2": 12},
        })
    assert missing.value.http_status == 422

    created = policy.update_tenant_policy({"userId": "91"}, tid, _body())
    assert created["tenantOverride"]["enabled"] is True
    assert created["tenantOverride"]["rowVersion"] == 1
    assert created["effective"]["configured"] is True
    assert created["effective"]["source"] == "TENANT"
    assert created["effective"]["version"] == "SLA-SCHOOL-2026-09"
    assert created["effective"]["targetsHours"] == {"P0": 1.0, "P1": 4.0, "P2": 12.0, "P3": 36.0}


def test_m8_sla_stale_expected_version_is_409_and_current_version_advances(db_mode):
    from app.services import module_commerce_sla_policy_service as policy

    tid = BASE + 2
    _seed_tenant(tid)
    first = policy.update_tenant_policy({"userId": "92"}, tid, _body())
    with pytest.raises(AppException) as stale:
        policy.update_tenant_policy({"userId": "92"}, tid, _body(0, version="SLA-STALE"))
    assert stale.value.http_status == 409
    assert stale.value.details["currentVersion"] == 1
    second = policy.update_tenant_policy({"userId": "92"}, tid, {
        **_body(first["tenantOverride"]["rowVersion"], version="SLA-SCHOOL-2026-10"),
        "targetsHours": {"P0": 0.5, "P1": 3, "P2": 10, "P3": 30},
    })
    assert second["tenantOverride"]["rowVersion"] == 2
    assert second["effective"]["targetsHours"]["P0"] == 0.5


def test_m8_sla_reset_disables_tenant_override_and_falls_back_to_explicit_platform_default(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig
    from app.services import module_commerce_sla_policy_service as policy

    tid = BASE + 3
    _seed_tenant(tid)
    db = get_sessionmaker()()
    try:
        db.add(PlatformConfig(
            tenant_id=0, config_type="COMMERCIAL_SLA_POLICY", config_key="SUPPORT_TICKET",
            config_json={"version": "SLA-PLATFORM-DEFAULT", "targetsHours": {"P0": 2, "P1": 8, "P2": 24, "P3": 72}},
            enabled=True, status="ACTIVE",
        ))
        db.commit()
    finally:
        db.close()
    created = policy.update_tenant_policy({"userId": "93"}, tid, _body())
    reset = policy.reset_tenant_policy(
        {"userId": "93"}, tid,
        expected_version=created["tenantOverride"]["rowVersion"],
        reason="学校恢复采用平台合同默认SLA政策",
    )
    assert reset["tenantOverride"]["exists"] is True
    assert reset["tenantOverride"]["enabled"] is False
    assert reset["tenantOverride"]["rowVersion"] == 2
    assert reset["effective"]["configured"] is True
    assert reset["effective"]["source"] == "PLATFORM_DEFAULT"
    assert reset["effective"]["version"] == "SLA-PLATFORM-DEFAULT"


def test_m8_sla_reset_without_tenant_override_is_rejected(db_mode):
    from app.services import module_commerce_sla_policy_service as policy

    tid = BASE + 4
    _seed_tenant(tid)
    with pytest.raises(AppException) as caught:
        policy.reset_tenant_policy({"userId": "94"}, tid, expected_version=0, reason="没有覆盖时不应生成空记录")
    assert caught.value.http_status == 409


def test_m8_sla_critical_audit_failure_rolls_back_first_create(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig
    from app.services import audit_log
    from app.services import module_commerce_sla_policy_service as policy
    from sqlalchemy import func, select

    tid = BASE + 5
    _seed_tenant(tid)
    monkeypatch.setattr(audit_log, "record_critical_in_session", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("audit unavailable")))
    with pytest.raises(RuntimeError):
        policy.update_tenant_policy({"userId": "95"}, tid, _body())
    db = get_sessionmaker()()
    try:
        count = int(db.scalar(select(func.count(PlatformConfig.id)).where(
            PlatformConfig.tenant_id == tid,
            PlatformConfig.config_type == "COMMERCIAL_SLA_POLICY",
        )) or 0)
        assert count == 0
    finally:
        db.close()
