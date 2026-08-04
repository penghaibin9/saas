"""SYS-01 学校治理总览：只读聚合 SYS-02~SYS-20 各权威服务的既有结论。

不建任何新表、不重复实现任何一个域的判定逻辑——每个字段都直接调用对应域
已有的只读函数，本服务只做拼装和统一的"风险/待办"归并，避免总览页变成
与各治理域并列的第二数据源。
"""
from __future__ import annotations

from app.core.context import current_tenant_id


def governance_overview(tenant_id: int | None = None) -> dict:
    from app.models.security_change import (CHANGE_APPROVED, CHANGE_PENDING_REVIEW,
                                             CHANGE_SCHEDULED)
    from app.services import system_governance_service as gov
    from app.services.audit_evidence_service import governance_overview as audit_overview
    from app.services.go_live_check_service import run_go_live_checks
    from app.services.master_data_governance_service import list_domains
    from app.services.module_access_service import module_access_state
    from app.services.security_change_service import list_change_sets

    tid = int(tenant_id or current_tenant_id() or 0)

    go_live = run_go_live_checks(tid)

    jobs = gov.list_sync_jobs()
    failed_jobs = [j for j in jobs if j.get("status") == "FAILED"]
    integrations = gov.list_integrations()

    modules = {}
    for mk in ("studentAffairs", "academicAffairs", "graduationDesign",
               "internship", "employment", "orientation"):
        modules[mk] = module_access_state(tid, mk) if tid else {"entitled": False, "enabled": False}

    pending_security_changes: list[dict] = []
    try:
        change_sets = list_change_sets(tenant_id=tid).get("items", [])
        pending_security_changes = [
            c for c in change_sets
            if c.get("status") in (CHANGE_PENDING_REVIEW, CHANGE_APPROVED, CHANGE_SCHEDULED)
        ]
    except Exception:
        pending_security_changes = []

    domains_without_owner: list[str] = []
    domains_with_open_issues: list[str] = []
    try:
        md = list_domains(tenant_id=tid)
        domains_without_owner = list(md.get("domainsWithoutOwner") or [])
        domains_with_open_issues = [
            d["domainCode"] for d in md.get("list", []) if d.get("openIssues")
        ]
    except Exception:
        pass

    try:
        audit = audit_overview()
    except Exception:
        audit = {}

    risks: list[dict] = []
    if go_live["summary"]["blocker"]:
        risks.append({"level": "HIGH", "sourceCard": "SYS-01",
                      "text": f"{go_live['summary']['blocker']} 项上线检查阻断未通过"})
    if failed_jobs:
        risks.append({"level": "MEDIUM", "sourceCard": "SYS-16",
                      "text": f"{len(failed_jobs)} 个同步/后台任务失败"})
    if pending_security_changes:
        risks.append({"level": "MEDIUM", "sourceCard": "SYS-09",
                      "text": f"{len(pending_security_changes)} 项安全变更待审核或待激活"})
    if domains_without_owner:
        risks.append({"level": "LOW", "sourceCard": "SYS-17",
                      "text": f"{len(domains_without_owner)} 个主数据域未指定责任人"})
    if audit.get("auditGapCount"):
        risks.append({"level": "MEDIUM", "sourceCard": "SYS-21",
                      "text": f"{audit['auditGapCount']} 条高危操作审计证据不完整"})

    todos = [c for c in go_live["items"] if c["status"] in ("BLOCKER", "ADVISORY")]
    for c in pending_security_changes:
        todos.append({
            "code": f"security_change_{c.get('id')}", "title": "安全变更待处理",
            "status": "ADVISORY", "detail": c.get("title") or f"变更集 #{c.get('id')}",
            "impact": "", "recommendedAction": "在安全变更中心处理",
        })

    return {
        "tenantId": tid,
        "goLive": {"canGoLive": go_live["canGoLive"], "summary": go_live["summary"]},
        "moduleHealth": modules,
        "configGaps": [c for c in go_live["items"] if c["status"] in ("BLOCKER", "ADVISORY")],
        "syncFailures": failed_jobs[:20],
        "integrationsRegistered": len(integrations),
        "securityRisks": risks,
        "pendingItems": todos[:20],
        "securityChangeGovernance": {
            "pendingCount": len(pending_security_changes),
            "items": pending_security_changes[:10],
        },
        "masterDataGovernance": {
            "domainsWithoutOwner": domains_without_owner,
            "domainsWithOpenIssues": domains_with_open_issues,
        },
        "auditGovernance": audit,
    }
