"""PLAT-14 数据治理、集成目录与合规证据（真库）。

跨租户聚合三块权威判定，重点验证：①主数据治理缺口是逐户真实求和，非重新
判定；②合规证据缺口只暴露 auditId/action/missing，绝不把审计明细（reason
原文、operator、resource）透传到平台运营页面（隐私边界）；③集成目录确实
逐户切换过租户上下文才能拿到各校数据，且用完必须还原，不遗留污染；
④仅平台超管可访问。
"""
from __future__ import annotations

import pytest

TID_A = 1000000000000000051   # 有一个数据域已指定责任人
TID_B = 1000000000000000052   # bootstrap 但未指定任何责任人


@pytest.fixture()
def two_tenants(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services import master_data_governance_service as md

    db = get_sessionmaker()()
    try:
        for tid, name in ((TID_A, "已治理学校"), (TID_B, "未治理学校")):
            if db.get(Tenant, tid) is None:
                db.add(Tenant(id=tid, tenant_code=f"plat14-{tid}", school_name=name, status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    md.bootstrap_defaults(tenant_id=TID_A)
    md.bootstrap_defaults(tenant_id=TID_B)
    md.set_domain_owner(md.DOMAIN_STUDENT, owner_user_id=1, reason="学工处长期负责学生主档",
                        tenant_id=TID_A)
    yield {"a": TID_A, "b": TID_B}


# ── PLAT14-T01：数据治理缺口是逐户真实求和，未治理学校要进入榜单 ──────────
def test_t01_data_governance_gaps_are_real_per_tenant_sums(two_tenants):
    from app.services import master_data_governance_service as md
    from app.services import platform_governance_service as pg

    board = pg.governance_overview()
    domains_a = md.list_domains(tenant_id=TID_A)
    domains_b = md.list_domains(tenant_id=TID_B)
    expected_no_owner = len(domains_a["domainsWithoutOwner"]) + len(domains_b["domainsWithoutOwner"])
    assert board["dataGovernance"]["domainsWithoutOwnerTotal"] >= expected_no_owner

    gap_ids = [t["tenantId"] for t in board["dataGovernance"]["tenantsWithGaps"]]
    assert str(TID_B) in gap_ids
    row_b = next(t for t in board["dataGovernance"]["tenantsWithGaps"] if t["tenantId"] == str(TID_B))
    row_a = next((t for t in board["dataGovernance"]["tenantsWithGaps"] if t["tenantId"] == str(TID_A)), None)
    if row_a is not None:  # A 仍可能有其它未指定责任人的域，只要求 B 的缺口不少于 A
        assert row_b["domainsWithoutOwner"] >= row_a["domainsWithoutOwner"]


# ── PLAT14-T02：合规证据缺口绝不透传审计明细（隐私边界）──────────────────
def test_t02_compliance_gaps_never_leak_raw_audit_detail(two_tenants):
    from app.core.context import set_current_user, set_tenant
    from app.services import audit_log
    from app.services import platform_governance_service as pg

    set_tenant({"tenantId": str(TID_A)})
    set_current_user({"userId": "u-secret", "realName": "秘密操作人"})
    try:
        audit_log.record("PLATFORM_GOVERNANCE_FORCE_DELETE", "domain:secret-object",
                         detail={}, result="SUCCESS")  # 故意不带 reason，制造一条缺口
    finally:
        set_current_user(None)
        set_tenant(None)

    board = pg.governance_overview()
    assert board["complianceEvidence"]["gapCount"] >= 1
    for gap in board["complianceEvidence"]["gaps"]:
        assert set(gap.keys()) <= {"auditId", "action", "missing"}
        assert "秘密操作人" not in str(gap)
        assert "domain:secret-object" not in str(gap)


# ── PLAT14-T03：集成目录逐户切换租户上下文，用完必须还原不遗留污染 ────────
def test_t03_integration_catalog_switches_and_restores_tenant_context(two_tenants, monkeypatch):
    from app.core.context import current_tenant_id
    from app.services import platform_governance_service as pg

    seen_tenants = []

    def fake_list_integrations():
        seen_tenants.append(current_tenant_id())
        return [{"id": "x"}] if current_tenant_id() == str(TID_B) else []

    monkeypatch.setattr("app.services.system_governance_service.list_integrations", fake_list_integrations)
    assert current_tenant_id() is None

    board = pg.governance_overview()
    assert str(TID_A) in seen_tenants
    assert str(TID_B) in seen_tenants
    assert board["integrationCatalog"]["registeredCount"] >= 1
    assert current_tenant_id() is None  # 不遗留租户上下文污染后续请求


# ── HTTP：仅平台超管可访问 ──────────────────────────────────────────────
def test_http_governance_overview_requires_platform_super_admin(client, two_tenants):
    from app.core.security import create_access_token

    school_token = create_access_token({
        "userId": "u-plat14-school", "realName": "校级管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(TID_A), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    r = client.get("/api/v1/platform/governance/overview",
                   headers={"Authorization": f"Bearer {school_token}"})
    assert r.status_code == 403

    admin_token = create_access_token({
        "userId": "u-plat14-owner", "realName": "平台超管", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "0", "activeContextId": "ctx",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    r = client.get("/api/v1/platform/governance/overview",
                   headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    assert body["code"] == 0, body
    for key in ("tenantCount", "dataGovernance", "integrationCatalog", "complianceEvidence"):
        assert key in body["data"], key
