"""PLAT-01 platform overview with explicit source quality.

W6 keeps the existing business counters for compatibility but overrides the
fields that must come from stronger authorities: tenant lifecycle uses the
strict effective-state resolver and storage uses FileObject/file-governance
aggregation. Every optional source carries OK/DEGRADED/UNKNOWN rather than
silently turning an exception into zero risk.
"""
from __future__ import annotations

from datetime import datetime


def _source(callable_):
    try:
        payload = callable_()
        return {"status": "OK", "message": "", "payload": payload or {}}
    except Exception as exc:
        return {"status": "UNKNOWN", "message": str(exc)[:300], "payload": {}}


def _tenant_lifecycle_projection() -> dict:
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services.tenant_effective_state_service import get_effective_state

    db = get_sessionmaker()()
    try:
        tenants = db.scalars(select(Tenant).where(Tenant.is_deleted.is_(False))).all()
    finally:
        db.close()

    counts = {"trial": 0, "active": 0, "expired": 0, "disabled": 0, "readonly": 0, "provisioning": 0, "archived": 0}
    unresolved = []
    for tenant in tenants:
        try:
            state = get_effective_state(int(tenant.id), strict=True)
            status = str(state.get("effectiveStatus") or "unresolved").lower()
            if status == "unresolved":
                raise RuntimeError("tenant effective status unresolved")
            counts[status] = counts.get(status, 0) + 1
        except Exception as exc:
            unresolved.append({
                "tenantId": str(tenant.id),
                "tenantName": tenant.school_name,
                "error": str(exc)[:300],
            })
    return {
        "tenantTotal": len(tenants),
        "counts": counts,
        "tenantUnresolved": len(unresolved),
        "unresolvedTenants": unresolved,
    }


def overview() -> dict:
    from app.services import platform_service
    from app.services.change_management_service import governance_overview as changes_overview
    from app.services.customer_health_service import governance_overview as customer_success_overview
    from app.services.foundation_operations_service import foundation_overview
    from app.services.incident_service import governance_overview as incidents_overview
    from app.services.service_catalog_service import governance_overview as services_overview

    business = platform_service.overview()
    lifecycle = _source(_tenant_lifecycle_projection)
    foundation = _source(foundation_overview)
    services = _source(services_overview)
    incidents = _source(incidents_overview)
    changes = _source(changes_overview)
    customer_success = _source(customer_success_overview)

    if foundation["status"] == "OK":
        coverage = foundation["payload"].get("coverage") or {}
        if str(coverage.get("status") or "OK").upper() != "OK":
            foundation["status"] = "DEGRADED"
            foundation["message"] = f"文件治理仅覆盖 {coverage.get('successTenantCount', 0)}/{coverage.get('totalTenantCount', 0)} 所学校"

    lifecycle_payload = lifecycle["payload"]
    lifecycle_counts = lifecycle_payload.get("counts") or {}
    if lifecycle["status"] == "OK" and int(lifecycle_payload.get("tenantUnresolved") or 0) > 0:
        lifecycle["status"] = "DEGRADED"
        lifecycle["message"] = f"{lifecycle_payload['tenantUnresolved']} 所学校的有效状态无法确定"

    file_foundation = foundation["payload"].get("fileFoundation") or {}
    storage_bytes = int(file_foundation.get("totalBytes") or 0) if foundation["status"] != "UNKNOWN" else None

    operational_risks: list[dict] = []
    incident_payload = incidents["payload"]
    service_payload = services["payload"]
    change_payload = changes["payload"]
    if incident_payload.get("p0p1ActiveCount"):
        operational_risks.append({"level": "HIGH", "sourceCard": "PLAT-09", "text": f"{incident_payload['p0p1ActiveCount']} 个 P0/P1 事件仍在进行中"})
    if incident_payload.get("unacknowledgedCount"):
        operational_risks.append({"level": "MEDIUM", "sourceCard": "PLAT-09", "text": f"{incident_payload['unacknowledgedCount']} 个事件尚未确认"})
    if service_payload.get("degradedCount"):
        operational_risks.append({"level": "HIGH", "sourceCard": "PLAT-08", "text": f"{service_payload['degradedCount']} 个平台服务处于降级状态"})
    if service_payload.get("noOwnerCount"):
        operational_risks.append({"level": "MEDIUM", "sourceCard": "PLAT-08", "text": f"{service_payload['noOwnerCount']} 个平台服务未指定责任人"})
    if change_payload.get("pendingApprovalCount"):
        operational_risks.append({"level": "MEDIUM", "sourceCard": "PLAT-11", "text": f"{change_payload['pendingApprovalCount']} 项变更待审批"})
    if change_payload.get("freezeConflictCount"):
        operational_risks.append({"level": "HIGH", "sourceCard": "PLAT-11", "text": f"{change_payload['freezeConflictCount']} 项变更与学校冻结窗口冲突"})

    quality_sources = {
        "tenantLifecycle": {"status": lifecycle["status"], "message": lifecycle["message"]},
        "fileFoundation": {
            "status": foundation["status"], "message": foundation["message"],
            "coverage": foundation["payload"].get("coverage") or None,
        },
        "serviceCatalog": {"status": services["status"], "message": services["message"]},
        "incidents": {"status": incidents["status"], "message": incidents["message"]},
        "changes": {"status": changes["status"], "message": changes["message"]},
        "customerSuccess": {"status": customer_success["status"], "message": customer_success["message"]},
    }
    for source_name, quality in quality_sources.items():
        if quality["status"] == "UNKNOWN":
            operational_risks.append({
                "level": "MEDIUM", "sourceCard": "DATA_QUALITY",
                "text": f"{source_name} 数据源当前未知，不能将缺失解释为 0 或健康",
            })

    complete = all(item["status"] == "OK" for item in quality_sources.values())
    return {
        **business,
        "sourceAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "revision": "PLATFORM_OVERVIEW_V2",
        "dataQuality": {"complete": complete, "sources": quality_sources},
        "tenantTotal": lifecycle_payload.get("tenantTotal", business.get("tenantTotal")),
        "tenantTrial": lifecycle_counts.get("trial", business.get("tenantTrial", 0)),
        "tenantActive": lifecycle_counts.get("active", business.get("tenantActive", 0)),
        "tenantExpired": lifecycle_counts.get("expired", business.get("tenantExpired", 0)),
        "tenantDisabled": lifecycle_counts.get("disabled", business.get("tenantDisabled", 0)),
        "tenantUnresolved": int(lifecycle_payload.get("tenantUnresolved") or 0) if lifecycle["status"] != "UNKNOWN" else None,
        "unresolvedTenants": lifecycle_payload.get("unresolvedTenants") or [],
        "storageUsedBytes": storage_bytes,
        "storageUsedMb": round(storage_bytes / 1048576, 2) if storage_bytes is not None else None,
        "fileDirStatus": "LEGACY_NOT_AUTHORITATIVE",
        "systemHealth": "UP" if complete else "DEGRADED",
        "serviceCatalog": service_payload,
        "incidents": incident_payload,
        "changes": change_payload,
        "customerSuccess": customer_success["payload"],
        "operationalRisks": operational_risks,
    }
