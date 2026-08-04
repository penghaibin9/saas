"""PLAT-01 平台经营、客户成功与运行总览（真库）。

角色边界已由 test_platform.py 的 §一 覆盖（非平台超管一律 403），这里只
新增 PLAT-01 本卡真正新增的能力：总览聚合 PLAT-08/09/11 已交付的
governance_overview()，并从中派生跨域运行风险；同时保留一条角色冒烟，
确认新字段没有绕开既有的平台超管强校验。
"""
from __future__ import annotations

from app.core.security import create_access_token

MAIN_TID = 1000000000000000031


def _owner_headers():
    token = create_access_token({
        "userId": "u-plat01-owner", "realName": "平台超管", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "0", "activeContextId": "ctx",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    return {"Authorization": f"Bearer {token}"}


def _school_admin_headers():
    token = create_access_token({
        "userId": "u-plat01-school", "realName": "校级管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN_TID), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    return {"Authorization": f"Bearer {token}"}


# ── PLAT01-T01：总览聚合服务目录 / 事件 / 变更的既有结论，不重新判定 ─────────
def test_t01_overview_aggregates_service_incident_change_governance(db_mode):
    from app.services import platform_overview_service as ov
    from app.services.change_management_service import governance_overview as changes_overview
    from app.services.incident_service import governance_overview as incidents_overview
    from app.services.service_catalog_service import governance_overview as services_overview

    board = ov.overview()
    assert board["serviceCatalog"] == services_overview()
    assert board["incidents"] == incidents_overview()
    assert board["changes"] == changes_overview()
    assert "tenantTotal" in board  # 经营指标仍保留（platform_service.overview() 透传）


# ── PLAT01-T02：单点服务降级 / 待审批变更要转成跨域运行风险 ──────────────────
def test_t02_degraded_service_and_pending_change_become_operational_risks(db_mode, monkeypatch):
    from app.services import platform_overview_service as ov

    monkeypatch.setattr(
        "app.services.service_catalog_service.governance_overview",
        lambda: {"degradedCount": 1, "degradedServices": ["svc_auth"], "noOwnerCount": 0})
    monkeypatch.setattr(
        "app.services.incident_service.governance_overview",
        lambda: {"activeCount": 0, "p0p1ActiveCount": 0, "unacknowledgedCount": 0})
    monkeypatch.setattr(
        "app.services.change_management_service.governance_overview",
        lambda: {"pendingApprovalCount": 2, "freezeConflictCount": 0})

    board = ov.overview()
    risks = {(r["sourceCard"], r["level"]) for r in board["operationalRisks"]}
    assert ("PLAT-08", "HIGH") in risks
    assert ("PLAT-11", "MEDIUM") in risks


def test_t02b_all_domains_healthy_means_no_operational_risks(db_mode, monkeypatch):
    from app.services import platform_overview_service as ov

    monkeypatch.setattr(
        "app.services.service_catalog_service.governance_overview",
        lambda: {"degradedCount": 0, "noOwnerCount": 0})
    monkeypatch.setattr(
        "app.services.incident_service.governance_overview",
        lambda: {"activeCount": 0, "p0p1ActiveCount": 0, "unacknowledgedCount": 0})
    monkeypatch.setattr(
        "app.services.change_management_service.governance_overview",
        lambda: {"pendingApprovalCount": 0, "freezeConflictCount": 0})

    board = ov.overview()
    assert board["operationalRisks"] == []


# ── PLAT01-T03：角色边界回归（不因新字段绕开强校验）───────────────────────────
def test_t03_school_admin_still_403_on_enriched_overview(client, db_mode):
    r = client.get("/api/v1/platform/overview", headers=_school_admin_headers())
    body = r.json()
    assert r.status_code == 403 and body["bizCode"] == "NO_PERMISSION"


def test_http_overview_returns_new_fields(client, db_mode):
    r = client.get("/api/v1/platform/overview", headers=_owner_headers())
    body = r.json()
    assert body["code"] == 0, body
    for key in ("serviceCatalog", "incidents", "changes", "operationalRisks", "tenantTotal"):
        assert key in body["data"], key
