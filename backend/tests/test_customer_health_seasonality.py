"""PLAT-05 客户健康、工单、培训与续费（真库）。

健康分不落表，直接判定：①受 P0/P1 活跃事件影响的学校必须是 CRITICAL；
②多个未关闭工单或上线检查未过必须是 AT_RISK；③健康的学校保持 HEALTHY；
④工单流转有乐观锁；⑤总览是逐户真实统计，不是写死的示例数据。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException

TID_CRITICAL = 1000000000000000061   # 受 P0 事件影响
TID_AT_RISK = 1000000000000000062    # 3 个未关闭工单
TID_HEALTHY = 1000000000000000063    # 无异常


@pytest.fixture()
def three_tenants(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.models.incident import Incident, IncidentTenant
    from app.services import platform_service as platform

    db = get_sessionmaker()()
    try:
        for tid, name in ((TID_CRITICAL, "危机学校"), (TID_AT_RISK, "风险学校"), (TID_HEALTHY, "健康学校")):
            if db.get(Tenant, tid) is None:
                db.add(Tenant(id=tid, tenant_code=f"plat05-{tid}", school_name=name, status="ACTIVE"))
        db.flush()

        incident = Incident(title="核心接口不可用", severity="P0", status="MITIGATING",
                            affected_service_codes_json=["svc_api"])
        db.add(incident)
        db.flush()
        db.add(IncidentTenant(incident_id=incident.id, tenant_id=TID_CRITICAL, impact_type="DIRECT"))
        db.commit()
    finally:
        db.close()

    for tid in (TID_CRITICAL, TID_AT_RISK, TID_HEALTHY):
        platform.put_config_json(tid, "TENANT_META", "-", {"status": "active", "packageCode": "professional"})

    yield {"critical": TID_CRITICAL, "at_risk": TID_AT_RISK, "healthy": TID_HEALTHY}


# ── PLAT05-T01：受活跃 P0 事件影响的学校必须是 CRITICAL ─────────────────────
def test_t01_tenant_with_active_p0_incident_is_critical(three_tenants):
    from app.services import customer_health_service as cs

    score = cs.health_score(TID_CRITICAL)
    assert score["level"] == "CRITICAL"
    assert score["activeIncidentSeverity"] == "P0"
    assert score["reasons"]


# ── PLAT05-T02：3 个未关闭工单要判定为 AT_RISK，工单闭合后不再计入 ──────────
def test_t02_three_open_tickets_makes_tenant_at_risk_and_closing_reduces(three_tenants):
    from app.services import customer_health_service as cs

    created = []
    for i in range(3):
        t = cs.create_ticket(tenant_id=TID_AT_RISK, title=f"工单{i}", severity="P2")
        created.append(t)
    score = cs.health_score(TID_AT_RISK)
    assert score["level"] == "AT_RISK"
    assert score["openTickets"] == 3

    for t in created:
        cs.transition_ticket(int(t["id"]), status="RESOLVED", expected_version=t["version"])
    score_after = cs.health_score(TID_AT_RISK)
    assert score_after["openTickets"] == 0


def test_t02b_healthy_tenant_has_no_reasons(three_tenants):
    from app.services import customer_health_service as cs

    score = cs.health_score(TID_HEALTHY)
    assert score["level"] == "HEALTHY"
    assert score["reasons"] == []


# ── PLAT05-T03：工单流转具备乐观锁，版本冲突要报 409 ───────────────────────
def test_t03_ticket_transition_optimistic_lock(three_tenants):
    from app.services import customer_health_service as cs

    ticket = cs.create_ticket(tenant_id=TID_HEALTHY, title="并发测试工单", severity="P1")
    cs.transition_ticket(int(ticket["id"]), status="IN_PROGRESS", expected_version=ticket["version"])
    with pytest.raises(AppException) as exc:
        cs.transition_ticket(int(ticket["id"]), status="RESOLVED", expected_version=ticket["version"])
    assert exc.value.http_status == 409


def test_t03b_cancelled_training_cannot_be_completed(three_tenants):
    from app.models.customer_success import TrainingRecord
    from app.services import customer_health_service as cs

    training = cs.create_training(tenant_id=TID_HEALTHY, topic="上线培训",
                                  scheduled_at=datetime.utcnow() + timedelta(days=1))
    with cs._session() as db:
        row = db.get(TrainingRecord, int(training["id"]))
        row.status = "CANCELLED"
        db.commit()
    with pytest.raises(AppException) as exc:
        cs.complete_training(int(training["id"]), attendee_count=5,
                             expected_version=training["version"])
    assert exc.value.code == "STATE_TRANSITION_DENIED"


# ── PLAT05-T04：总览是逐户真实统计 ─────────────────────────────────────────
def test_t04_governance_overview_reflects_real_per_tenant_state(three_tenants):
    from app.services import customer_health_service as cs

    cs.create_ticket(tenant_id=TID_AT_RISK, title="待关闭工单", severity="P2")
    board = cs.governance_overview()
    assert board["healthDistribution"]["CRITICAL"] >= 1
    assert board["openTicketsTotal"] >= 1
    critical_ids = [t["tenantId"] for t in board["criticalTenants"]]
    assert str(TID_CRITICAL) in critical_ids


# ── HTTP：仅平台超管可访问 ──────────────────────────────────────────────
def test_http_customer_success_requires_platform_super_admin(client, three_tenants):
    from app.core.security import create_access_token

    school_token = create_access_token({
        "userId": "u-plat05-school", "realName": "校级管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(TID_HEALTHY), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    r = client.get("/api/v1/platform/customer-success/overview",
                   headers={"Authorization": f"Bearer {school_token}"})
    assert r.status_code == 403

    admin_token = create_access_token({
        "userId": "u-plat05-owner", "realName": "平台超管", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "0", "activeContextId": "ctx",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    r = client.get("/api/v1/platform/customer-success/overview",
                   headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    assert body["code"] == 0, body

    r = client.post("/api/v1/platform/support-tickets", headers={"Authorization": f"Bearer {admin_token}"},
                    json={"tenantId": str(TID_HEALTHY), "title": "HTTP冒烟工单", "severity": "P3"})
    assert r.json()["code"] == 0, r.json()
