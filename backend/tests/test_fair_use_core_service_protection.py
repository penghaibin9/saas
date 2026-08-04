"""PLAT-13 租户用量、容量、成本与公平使用（真库）。

覆盖：①用量快照的数字是真实聚合、幂等（同一天重复生成不产生第二条）；
②超出配额要真实检出（用可配置的低配额，不用堆 5000 条数据去撞默认值）；
③同一天重复评估更新同一条违规记录，不产生第二条；④连续多天超限要被
总览识别为"连续超限学校"（保护共享核心服务的关键信号）；⑤仅平台超管
可访问。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException

TID = 1000000000000000081


@pytest.fixture()
def tenant_ctx(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(id=TID, tenant_code=f"plat13-{TID}", school_name="用量测试学校", status="ACTIVE"))
            db.commit()
    finally:
        db.close()
    yield TID


def _record_audit_events(tenant_id: int, count: int) -> None:
    from app.services import audit_log

    set_tenant({"tenantId": str(tenant_id)})
    set_current_user({"userId": "u-metering", "realName": "用量测试"})
    try:
        for i in range(count):
            audit_log.record("FAIR_USE_TEST_EVENT", f"obj:{i}", detail={}, result="SUCCESS")
    finally:
        set_current_user(None)
        set_tenant(None)


# ── PLAT13-T01：快照数字是真实聚合，同一天重复生成幂等 ─────────────────────
def test_t01_snapshot_is_real_aggregate_and_idempotent(tenant_ctx):
    from app.services import tenant_metering_service as metering

    _record_audit_events(TID, 3)
    first = metering.capture_daily_snapshot(TID)
    assert first["auditEventCount"] >= 3

    _record_audit_events(TID, 2)
    second = metering.capture_daily_snapshot(TID)
    assert second["auditEventCount"] >= 5
    assert second["id"] == first["id"]  # 同一天，同一条记录被更新而非新增

    snapshots = metering.list_snapshots(TID, days=1)
    assert len([s for s in snapshots if s["snapshotDate"] == first["snapshotDate"]]) == 1


# ── PLAT13-T02：低配额下真实超限要被检出 ────────────────────────────────────
def test_t02_low_limit_triggers_real_violation(tenant_ctx):
    from app.services import fair_use_service as fu

    fu.upsert_limit(TID, resource_code="AUDIT_EVENTS_PER_DAY", daily_limit=2)
    _record_audit_events(TID, 5)
    result = fu.evaluate_tenant(TID)
    assert result["withinLimits"] is False
    hit = next(v for v in result["violations"] if v["resourceCode"] == "AUDIT_EVENTS_PER_DAY")
    assert hit["actualValue"] >= 5
    assert hit["limitValue"] == 2


def test_t02b_default_limit_is_not_triggered_by_small_volume(tenant_ctx):
    from app.services import fair_use_service as fu

    _record_audit_events(TID, 3)
    result = fu.evaluate_tenant(TID)
    assert result["withinLimits"] is True  # 默认配额 5000，远大于 3


# ── PLAT13-T03：同一天重复评估更新同一条记录，不产生第二条 ─────────────────
def test_t03_same_day_reevaluation_updates_not_duplicates(tenant_ctx):
    from app.services import fair_use_service as fu

    fu.upsert_limit(TID, resource_code="AUDIT_EVENTS_PER_DAY", daily_limit=1)
    _record_audit_events(TID, 2)
    fu.evaluate_tenant(TID)
    _record_audit_events(TID, 2)
    fu.evaluate_tenant(TID)

    violations = fu.list_violations(TID, days=1)
    same_resource = [v for v in violations if v["resourceCode"] == "AUDIT_EVENTS_PER_DAY"]
    assert len(same_resource) == 1
    assert same_resource[0]["actualValue"] >= 4


# ── PLAT13-T04：连续多天超限要被总览识别为连续超限学校 ─────────────────────
def test_t04_chronic_offender_detected_across_multiple_days(tenant_ctx):
    from app.db.session import get_sessionmaker
    from app.models.tenant_metering import TenantFairUseViolation
    from app.services import fair_use_service as fu

    today = datetime.utcnow().date()
    db = get_sessionmaker()()
    try:
        for delta in (0, 1, 2):
            db.add(TenantFairUseViolation(
                tenant_id=TID, resource_code="AUDIT_EVENTS_PER_DAY",
                violation_date=today - timedelta(days=delta),
                actual_value=999, limit_value=100, action_taken="LOGGED"))
        db.commit()
    finally:
        db.close()

    board = fu.governance_overview()
    offender = next((o for o in board["chronicOffenders"] if o["tenantId"] == str(TID)), None)
    assert offender is not None
    assert offender["violationDaysLast7"] >= 3


# ── HTTP：仅平台超管可访问 ──────────────────────────────────────────────
def test_http_fair_use_requires_platform_super_admin(client, tenant_ctx):
    from app.core.security import create_access_token

    school_token = create_access_token({
        "userId": "u-plat13-school", "realName": "校级管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    r = client.get("/api/v1/platform/fair-use/overview", headers={"Authorization": f"Bearer {school_token}"})
    assert r.status_code == 403

    admin_token = create_access_token({
        "userId": "u-plat13-owner", "realName": "平台超管", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "0", "activeContextId": "ctx",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = client.get("/api/v1/platform/fair-use/overview", headers=headers)
    body = r.json()
    assert body["code"] == 0, body

    r = client.post(f"/api/v1/platform/tenants/{TID}/usage-snapshots/capture", headers=headers)
    assert r.json()["code"] == 0, r.json()
