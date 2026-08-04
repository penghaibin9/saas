"""PLAT-06 公共底座运行中心：跨租户聚合 PR#25 文件底座与 PLAT-08 服务目录。

学校侧的容量/异常判定权威已经是 file_storage_governance_service（SYS-19
消费同一套函数）——这里只是站在平台运营视角，把它对每个租户逐条跑一遍再
求和、找出最需要关注的学校，不重新发明一套判定规则，也不新建表。
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
    for t in tenants:
        try:
            usage = filegov.usage_snapshot(tenant_id=t.id)
            anomalies = filegov.anomaly_snapshot(tenant_id=t.id)
            health = filegov.operational_health(tenant_id=t.id)
        except Exception:
            continue
        totals["totalBytes"] += usage.get("totalBytes") or 0
        totals["quotaBytes"] += usage.get("quotaBytes") or 0
        for k in ("quarantineOverOneHour", "scanErrors", "expiredPendingCleanup",
                  "cosUnverified", "unboundOver24Hours", "legalHoldFiles"):
            totals[k] += anomalies.get(k) or 0
        for k in ("scanBacklog", "failedFileJobs", "heldReservations", "expiredHeldReservations"):
            totals[k] += health.get(k) or 0
        anomaly_score = (
            (anomalies.get("quarantineOverOneHour") or 0)
            + (anomalies.get("scanErrors") or 0)
            + (anomalies.get("expiredPendingCleanup") or 0)
            + (anomalies.get("cosUnverified") or 0)
            + (health.get("failedFileJobs") or 0)
        )
        if anomaly_score:
            tenants_needing_attention.append({
                "tenantId": str(t.id), "tenantName": t.school_name, "anomalyScore": anomaly_score,
            })
    tenants_needing_attention.sort(key=lambda x: -x["anomalyScore"])

    try:
        services = services_overview()
    except Exception:
        services = {}

    risks: list[dict] = []
    if totals["scanErrors"]:
        risks.append({"level": "HIGH", "sourceCard": "SYS-19",
                      "text": f"全平台 {totals['scanErrors']} 个文件病毒扫描失败"})
    if totals["cosUnverified"]:
        risks.append({"level": "MEDIUM", "sourceCard": "SYS-19",
                      "text": f"全平台 {totals['cosUnverified']} 个文件对象存储未完成生产校验"})
    if totals["expiredPendingCleanup"]:
        risks.append({"level": "LOW", "sourceCard": "SYS-19",
                      "text": f"全平台 {totals['expiredPendingCleanup']} 个文件已到期待清理"})
    if totals["failedFileJobs"]:
        risks.append({"level": "MEDIUM", "sourceCard": "SYS-19",
                      "text": f"全平台 {totals['failedFileJobs']} 个文件后台任务失败"})
    if services.get("degradedCount"):
        risks.append({"level": "HIGH", "sourceCard": "PLAT-08",
                      "text": f"{services['degradedCount']} 个平台服务处于降级状态"})

    return {
        "tenantCount": len(tenants),
        "fileFoundation": totals,
        "tenantsNeedingAttention": tenants_needing_attention[:10],
        "serviceCatalog": services,
        "risks": risks,
    }
