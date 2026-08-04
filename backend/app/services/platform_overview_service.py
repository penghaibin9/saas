"""PLAT-01 经营、客户成功与运行总览：只读聚合所有已交付的平台权威服务。

经营指标（租户/学生/账号/审计）沿用既有 platform_service.overview()，不重复
实现。这里新增的是"运行"侧：服务目录（PLAT-08）、事件（PLAT-09）、变更
（PLAT-11）已经各自建好了 governance_overview()，总览页只是把这三份结论
和经营指标拼在一起，并从中挑出跨域的高优先级风险，不再另外判定。

尚未交付的平台域（PLAT-05 客户健康等）暂不聚合——待其建成后再接入，
不为了"总览要覆盖所有域"而提前编造字段。
"""
from __future__ import annotations


def overview() -> dict:
    from app.services import platform_service
    from app.services.change_management_service import governance_overview as changes_overview
    from app.services.incident_service import governance_overview as incidents_overview
    from app.services.service_catalog_service import governance_overview as services_overview

    business = platform_service.overview()

    try:
        services = services_overview()
    except Exception:
        services = {}
    try:
        incidents = incidents_overview()
    except Exception:
        incidents = {}
    try:
        changes = changes_overview()
    except Exception:
        changes = {}

    operational_risks: list[dict] = []
    if incidents.get("p0p1ActiveCount"):
        operational_risks.append({
            "level": "HIGH", "sourceCard": "PLAT-09",
            "text": f"{incidents['p0p1ActiveCount']} 个 P0/P1 事件仍在进行中",
        })
    if incidents.get("unacknowledgedCount"):
        operational_risks.append({
            "level": "MEDIUM", "sourceCard": "PLAT-09",
            "text": f"{incidents['unacknowledgedCount']} 个事件尚未确认",
        })
    if services.get("degradedCount"):
        operational_risks.append({
            "level": "HIGH", "sourceCard": "PLAT-08",
            "text": f"{services['degradedCount']} 个平台服务处于降级状态",
        })
    if services.get("noOwnerCount"):
        operational_risks.append({
            "level": "MEDIUM", "sourceCard": "PLAT-08",
            "text": f"{services['noOwnerCount']} 个平台服务未指定责任人",
        })
    if changes.get("pendingApprovalCount"):
        operational_risks.append({
            "level": "MEDIUM", "sourceCard": "PLAT-11",
            "text": f"{changes['pendingApprovalCount']} 项变更待审批",
        })
    if changes.get("freezeConflictCount"):
        operational_risks.append({
            "level": "HIGH", "sourceCard": "PLAT-11",
            "text": f"{changes['freezeConflictCount']} 项变更与学校冻结窗口冲突",
        })

    return {
        **business,
        "serviceCatalog": services,
        "incidents": incidents,
        "changes": changes,
        "operationalRisks": operational_risks,
    }
