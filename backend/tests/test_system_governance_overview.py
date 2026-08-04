"""SYS-01 学校治理总览（真库）。

只测聚合本身：总览页的每个字段必须直接来自对应权威服务的真实读取结果，
不允许总览页自己重新判定或另存一份"缺口/风险"结论（第二数据源）。
"""
import pytest

from app.core.context import set_tenant

MAIN_TID = 1000000000000000021


@pytest.fixture()
def tenant_ctx(db_mode):
    from app.models import Tenant
    from app.services import platform_service as platform
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, MAIN_TID) is None:
            db.add(Tenant(id=MAIN_TID, tenant_code=f"sys01-{MAIN_TID}", school_name="治理总览测试学校", status="ACTIVE"))
            db.commit()
    finally:
        db.close()
    platform.put_config_json(MAIN_TID, "TENANT_META", "-", {"status": "active", "packageCode": "professional"})
    set_tenant({"tenantId": str(MAIN_TID)})
    try:
        yield MAIN_TID
    finally:
        set_tenant(None)


# ── SYS01-T01：总览的上线检查结论必须与权威服务逐字一致（不是第二数据源）───────
def test_t01_go_live_summary_matches_authoritative_service(tenant_ctx):
    from app.services import system_governance_overview_service as ov
    from app.services.go_live_check_service import run_go_live_checks

    board = ov.governance_overview(tenant_id=MAIN_TID)
    authoritative = run_go_live_checks(MAIN_TID)
    assert board["goLive"]["summary"] == authoritative["summary"]
    assert board["goLive"]["canGoLive"] == authoritative["canGoLive"]


# ── SYS01-T02：SYS-09 待审核/待激活的安全变更要出现在待办与风险里 ─────────────
def test_t02_pending_security_changes_surface_in_overview(tenant_ctx, monkeypatch):
    from app.services import security_change_service as sec
    from app.services import system_governance_overview_service as ov

    monkeypatch.setattr(sec, "list_change_sets", lambda *, tenant_id=None: {
        "items": [{"id": 9001, "status": "PENDING_REVIEW", "title": "临时提权测试"}],
        "currentRevision": 0,
    })
    board = ov.governance_overview(tenant_id=MAIN_TID)
    assert board["securityChangeGovernance"]["pendingCount"] == 1
    assert any(t["code"] == "security_change_9001" for t in board["pendingItems"])
    assert any(r["sourceCard"] == "SYS-09" for r in board["securityRisks"])


def test_t02b_no_pending_security_changes_means_no_sys09_risk(tenant_ctx, monkeypatch):
    from app.services import security_change_service as sec
    from app.services import system_governance_overview_service as ov

    monkeypatch.setattr(sec, "list_change_sets", lambda *, tenant_id=None: {"items": [], "currentRevision": 0})
    board = ov.governance_overview(tenant_id=MAIN_TID)
    assert board["securityChangeGovernance"]["pendingCount"] == 0
    assert not any(r["sourceCard"] == "SYS-09" for r in board["securityRisks"])


# ── SYS01-T03：SYS-17 未指定责任人的主数据域要出现在治理总览 ──────────────────
def test_t03_master_data_domains_without_owner_surface(tenant_ctx):
    from app.services import master_data_governance_service as md
    from app.services import system_governance_overview_service as ov

    created = md.bootstrap_defaults(tenant_id=MAIN_TID)
    assert created["domains"] > 0  # 首次装入内置数据域，全部尚无责任人

    board = ov.governance_overview(tenant_id=MAIN_TID)
    assert board["masterDataGovernance"]["domainsWithoutOwner"]
    assert any(r["sourceCard"] == "SYS-17" for r in board["securityRisks"])


# ── SYS01-T04：SYS-21 审计证据缺口要透传（不重复实现判定逻辑）────────────────
def test_t04_audit_governance_reuses_sys21_service_output_verbatim(tenant_ctx):
    from app.services import audit_evidence_service as evid
    from app.services import system_governance_overview_service as ov

    board = ov.governance_overview(tenant_id=MAIN_TID)
    assert board["auditGovernance"] == evid.governance_overview()


# ── HTTP 端点冒烟 ────────────────────────────────────────────────────────────
def test_http_overview_board(client, tenant_ctx):
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": "u-overview-http", "realName": "系统管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN_TID), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/system/overview-board", headers=headers)
    body = r.json()
    assert body["code"] == 0, body
    data = body["data"]
    for key in ("moduleHealth", "configGaps", "syncFailures", "securityRisks",
                "pendingItems", "goLive", "securityChangeGovernance",
                "masterDataGovernance", "auditGovernance"):
        assert key in data, key
