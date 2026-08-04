"""PLAT-14 数据治理、集成目录与合规证据：跨租户只读聚合。

三块内容各自复用已建成的权威判定，不重新实现：
- 数据治理：逐户调用 SYS-17 master_data_governance_service.list_domains() 后求和。
- 集成目录：逐户调用 SYS-20 system_governance_service.list_integrations()（该函数
  读取当前租户上下文，跨租户拉取需要显式切换 set_tenant，用完立即还原）。
- 合规证据：直接复用 SYS-21 audit_evidence_service.evaluate_evidence_completeness()——
  这是不依赖租户上下文的纯函数，喂入跨租户查询到的审计行即可，不重复实现高危动作判定。

PLAT-12 灾备尚未交付（依赖外部云资源，本阶段不建），暂不聚合备份证据。
"""
from __future__ import annotations


def governance_overview() -> dict:
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog, Tenant
    from app.services import master_data_governance_service as md
    from app.services import system_governance_service as gov
    from app.services.audit_evidence_service import evaluate_evidence_completeness

    db = get_sessionmaker()()
    try:
        tenants = db.scalars(select(Tenant).where(Tenant.is_deleted.is_(False))).all()
        # 复审发现：原来是"全平台最近1000条"，一所高活跃度学校的日常操作足够挤满
        # 1000条配额，导致其它学校同期的高危操作完全排不进这次完整性检查——
        # 合规证据本来就是为了不漏检，这样反而制造了盲区。改成按时间窗口（近7天）
        # 扫描，配合更高的行数上限做兜底，不再让"谁的日志量大"决定谁被检查。
        since = datetime.utcnow() - timedelta(days=7)
        recent_audit_rows = db.scalars(
            select(SecurityAuditLog).where(SecurityAuditLog.created_at >= since)
            .order_by(SecurityAuditLog.id.desc()).limit(20000)
        ).all()
    finally:
        db.close()

    audit_rows = [{
        "auditId": str(r.id), "action": r.action, "resource": r.resource or "",
        "actorId": r.operator_id, "tenantId": str(r.tenant_id),
        "requestId": r.trace_id, "detail": r.detail_json or {},
    } for r in recent_audit_rows]
    completeness = evaluate_evidence_completeness(audit_rows)

    domains_without_owner_total = 0
    open_issues_total = 0
    integrations_total = 0
    tenants_with_gaps: list[dict] = []
    for t in tenants:
        try:
            domains = md.list_domains(tenant_id=t.id)
        except Exception:
            domains = {"domainsWithoutOwner": [], "list": []}
        no_owner = len(domains.get("domainsWithoutOwner") or [])
        open_issues = sum(d.get("openIssues") or 0 for d in domains.get("list", []))
        domains_without_owner_total += no_owner
        open_issues_total += open_issues

        set_tenant({"tenantId": str(t.id)})
        try:
            integrations = gov.list_integrations()
        except Exception:
            integrations = []
        finally:
            set_tenant(None)
        integrations_total += len(integrations)

        if no_owner or open_issues:
            tenants_with_gaps.append({
                "tenantId": str(t.id), "tenantName": t.school_name,
                "domainsWithoutOwner": no_owner, "openIssues": open_issues,
            })
    tenants_with_gaps.sort(key=lambda x: -(x["domainsWithoutOwner"] + x["openIssues"]))

    return {
        "tenantCount": len(tenants),
        "dataGovernance": {
            "domainsWithoutOwnerTotal": domains_without_owner_total,
            "openIssuesTotal": open_issues_total,
            "tenantsWithGaps": tenants_with_gaps[:10],
        },
        "integrationCatalog": {
            "registeredCount": integrations_total,
        },
        "complianceEvidence": completeness,
    }
