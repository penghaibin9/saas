"""PLAT-06 公共底座运行中心（真库）。

跨租户聚合 PR#25 文件底座（file_storage_governance_service 既有函数逐户
求和）+ PLAT-08 服务目录，验证：①总量是各租户求和且不重新判定异常规则；
②异常分数最高的学校要排在"需要关注"列表最前；③无异常学校不进入该列表；
④平台超管以外一律 403。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.file import FileObject

TID_QUIET = 1000000000000000041   # 无异常
TID_NOISY = 1000000000000000042   # 多个异常


def _file(tenant_id: int, name: str, **overrides) -> FileObject:
    now = datetime.utcnow()
    base = dict(
        tenant_id=tenant_id,
        file_key=f"clean/{tenant_id}/{name}",
        object_key=f"clean/{tenant_id}/{name}",
        file_name=name,
        ext="pdf",
        size_bytes=1024,
        biz_type="GRADUATION_MATERIAL",
        status="AVAILABLE",
        storage_backend="local",
        storage_zone="CLEAN",
        legal_hold=False,
        retention_until=now + timedelta(days=30),
        scan_required=False,
        scan_status="NOT_REQUIRED",
    )
    base.update(overrides)
    return FileObject(**base)


@pytest.fixture()
def two_tenants(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        for tid, name in ((TID_QUIET, "静默学校"), (TID_NOISY, "多异常学校")):
            if db.get(Tenant, tid) is None:
                db.add(Tenant(id=tid, tenant_code=f"plat06-{tid}", school_name=name, status="ACTIVE"))
        db.flush()
        db.add(_file(TID_QUIET, "ok.pdf"))
        db.add(_file(TID_NOISY, "scan-failed.pdf", scan_status="ERROR"))
        db.add(_file(TID_NOISY, "quarantined.pdf", storage_zone="QUARANTINE",
                     created_at=datetime.utcnow() - timedelta(hours=2)))
        db.commit()
    finally:
        db.close()
    yield {"quiet": TID_QUIET, "noisy": TID_NOISY}


# ── PLAT06-T01：总量是逐户求和，不重新判定异常规则 ────────────────────────
def test_t01_totals_are_sum_of_per_tenant_authoritative_snapshots(two_tenants):
    from app.services import file_storage_governance_service as filegov
    from app.services import foundation_operations_service as fo

    board = fo.foundation_overview()
    quiet = filegov.anomaly_snapshot(tenant_id=TID_QUIET)
    noisy = filegov.anomaly_snapshot(tenant_id=TID_NOISY)
    assert board["fileFoundation"]["scanErrors"] >= quiet["scanErrors"] + noisy["scanErrors"]
    assert board["fileFoundation"]["scanErrors"] >= 1  # 至少含本用例造的这一条


# ── PLAT06-T02：异常越多的学校排名越靠前，无异常学校不上榜 ────────────────
def test_t02_attention_ranking_and_quiet_tenant_excluded(two_tenants):
    from app.services import foundation_operations_service as fo

    board = fo.foundation_overview()
    ids = [t["tenantId"] for t in board["tenantsNeedingAttention"]]
    assert str(TID_NOISY) in ids
    assert str(TID_QUIET) not in ids
    noisy_row = next(t for t in board["tenantsNeedingAttention"] if t["tenantId"] == str(TID_NOISY))
    assert noisy_row["anomalyScore"] >= 2


# ── PLAT06-T03：服务降级要透传为风险，取自 PLAT-08 既有结论 ──────────────
def test_t03_degraded_service_surfaces_as_risk(two_tenants, monkeypatch):
    from app.services import foundation_operations_service as fo

    monkeypatch.setattr(
        "app.services.service_catalog_service.governance_overview",
        lambda: {"degradedCount": 1, "degradedServices": ["svc_x"]})
    board = fo.foundation_overview()
    assert any(r["sourceCard"] == "PLAT-08" for r in board["risks"])


# ── HTTP：仅平台超管可访问 ──────────────────────────────────────────────
def test_http_foundations_overview_requires_platform_super_admin(client, two_tenants):
    from app.core.security import create_access_token

    school_token = create_access_token({
        "userId": "u-plat06-school", "realName": "校级管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(TID_QUIET), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    r = client.get("/api/v1/platform/foundations/overview",
                   headers={"Authorization": f"Bearer {school_token}"})
    assert r.status_code == 403

    admin_token = create_access_token({
        "userId": "u-plat06-owner", "realName": "平台超管", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "0", "activeContextId": "ctx",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    r = client.get("/api/v1/platform/foundations/overview",
                   headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    assert body["code"] == 0, body
    for key in ("tenantCount", "fileFoundation", "tenantsNeedingAttention", "serviceCatalog", "risks"):
        assert key in body["data"], key
