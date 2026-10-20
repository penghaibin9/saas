"""PLAT-06 file/service foundation aggregation with explicit coverage.

Per-tenant file facts still come from file_storage_governance_service. W6 stops
silently dropping a tenant when that source fails: partial totals remain usable
only together with a DEGRADED coverage envelope.
"""
from __future__ import annotations


def foundation_overview() -> dict:
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services import file_storage_governance_service as filegov
    from app.services.service_catalog_service import governance_overview as services_overview

    db = get_sessionmaker()()
    try:
        tenants = db.scalars(select(Tenant).where(Tenant.is_deleted.is_(False))).all()
    finally:
        db.close()

    totals = {
        "totalBytes": 0, "quotaBytes": 0,
        "quarantineOverOneHour": 0, "scanErrors": 0, "expiredPendingCleanup": 0,
        "cosUnverified": 0, "unboundOver24Hours": 0, "legalHoldFiles": 0,
        "scanBacklog": 0, "failedFileJobs": 0, "heldReservations": 0, "expiredHeldReservations": 0,
    }
    tenants_needing_attention: list[dict] = []
    failed_tenants: list[dict] = []
    success_count = 0
    for tenant in tenants:
        try:
            usage = filegov.usage_snapshot(tenant_id=tenant.id)
            anomalies = filegov.anomaly_snapshot(tenant_id=tenant.id)
            health = filegov.operational_health(tenant_id=tenant.id)
        except Exception as exc:
            failed_tenants.append({
                "tenantId": str(tenant.id),
                "tenantName": tenant.school_name,
                "error": str(exc)[:300],
            })
            continue
        success_count += 1
        totals["totalBytes"] += usage.get("totalBytes") or 0
        totals["quotaBytes"] += usage.get("quotaBytes") or 0
        for key in ("quarantineOverOneHour", "scanErrors", "expiredPendingCleanup",
                    "cosUnverified", "unboundOver24Hours", "legalHoldFiles"):
            totals[key] += anomalies.get(key) or 0
        for key in ("scanBacklog", "failedFileJobs", "heldReservations", "expiredHeldReservations"):
            totals[key] += health.get(key) or 0
        anomaly_score = (
            (anomalies.get("quarantineOverOneHour") or 0)
            + (anomalies.get("scanErrors") or 0)
            + (anomalies.get("expiredPendingCleanup") or 0)
            + (anomalies.get("cosUnverified") or 0)
            + (health.get("failedFileJobs") or 0)
        )
        if anomaly_score:
            tenants_needing_attention.append({
                "tenantId": str(tenant.id), "tenantName": tenant.school_name, "anomalyScore": anomaly_score,
            })
    tenants_needing_attention.sort(key=lambda item: -item["anomalyScore"])

    try:
        services = services_overview()
        service_quality = {"status": "OK", "message": ""}
    except Exception as exc:
        services = {}
        service_quality = {"status": "UNKNOWN", "message": str(exc)[:300]}

    risks: list[dict] = []
    if totals["scanErrors"]:
        risks.append({"level": "HIGH", "sourceCard": "SYS-19", "text": f"全平台 {totals['scanErrors']} 个文件病毒扫描失败"})
    if totals["cosUnverified"]:
        risks.append({"level": "MEDIUM", "sourceCard": "SYS-19", "text": f"全平台 {totals['cosUnverified']} 个文件对象存储未完成生产校验"})
    if totals["expiredPendingCleanup"]:
        risks.append({"level": "LOW", "sourceCard": "SYS-19", "text": f"全平台 {totals['expiredPendingCleanup']} 个文件已到期待清理"})
    if totals["failedFileJobs"]:
        risks.append({"level": "MEDIUM", "sourceCard": "SYS-19", "text": f"全平台 {totals['failedFileJobs']} 个文件后台任务失败"})
    if services.get("degradedCount"):
        risks.append({"level": "HIGH", "sourceCard": "PLAT-08", "text": f"{services['degradedCount']} 个平台服务处于降级状态"})
    if failed_tenants:
        risks.append({
            "level": "MEDIUM", "sourceCard": "DATA_QUALITY",
            "text": f"{len(failed_tenants)} 所学校的文件治理数据未取得；当前文件总量为部分覆盖结果",
        })

    coverage_status = "OK" if not failed_tenants else "DEGRADED"
    return {
        "tenantCount": len(tenants),
        "fileFoundation": totals,
        "coverage": {
            "status": coverage_status,
            "totalTenantCount": len(tenants),
            "successTenantCount": success_count,
            "failedTenantCount": len(failed_tenants),
            "failedTenants": failed_tenants,
        },
        "tenantsNeedingAttention": tenants_needing_attention[:10],
        "serviceCatalog": services,
        "serviceCatalogQuality": service_quality,
        "risks": risks,
    }
