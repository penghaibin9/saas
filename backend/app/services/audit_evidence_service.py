"""SYS-21 安全审计、敏感操作与证据。

不新表——审计权威数据是既有 t_security_audit_log（db_service.audit_query 已经
实现真实查询，本文件复用它，不重复发明第二套审计存储）。证据包导出走既有
公共 ExportJob（t_export_job，PLAT-08/SYS-16 之前已验证过这张表的用法），
本文件只负责登记一条 ExportJob 并把"这次证据包的范围快照"计算清楚，真正
生成文件内容的执行器不在本卡白名单内，不在这里实现。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException
from app.services.db_service import _tid

# 高危动作的判定用动词特征匹配，而不是维护一份"全代码库高危动作清单"——
# 后者不可能穷举也不可能保持更新；只要新动作命名遵循这些动词，就自动纳入完整性检查。
HIGH_RISK_VERB_FRAGMENTS = (
    "DELETE", "ROLLBACK", "ROTATE", "APPROVE", "CANCEL", "COMPENSATE",
    "REVOKE", "GRANT", "TRANSITION", "WITHDRAW", "FORCE", "DISABLE",
    "RESET", "EXPORT",
)


def is_high_risk_action(action: str) -> bool:
    a = str(action or "").upper()
    return any(fragment in a for fragment in HIGH_RISK_VERB_FRAGMENTS)


def _completeness_gaps(row: dict) -> list[str]:
    """检查单条审计记录是否具备高危动作应有的字段；返回缺失字段名列表，空=完整。"""
    missing = []
    if not row.get("actorId"):
        missing.append("actorId")
    if not row.get("tenantId"):
        missing.append("tenantId")
    if not row.get("requestId"):
        missing.append("traceId")
    if not row.get("resource"):
        missing.append("object")
    detail = row.get("detail") or {}
    if not str(detail.get("reason") or "").strip():
        missing.append("reason")
    # version 不是每个高危动作都有对应的版本化实体；只在 detail 里已经出现
    # 类似 xxxVersion 的字段时才要求它非空，不强求所有动作都带 version。
    version_keys = [k for k in detail if k.lower().endswith("version")]
    if version_keys and not any(detail.get(k) not in (None, "") for k in version_keys):
        missing.append("version")
    return missing


def evaluate_evidence_completeness(rows: list[dict]) -> dict:
    """纯函数：对一批已经取出的审计记录（audit_query 的 dict 形状）做完整性判定。"""
    high_risk_rows = [r for r in rows if is_high_risk_action(r.get("action") or "")]
    gaps = []
    for r in high_risk_rows:
        missing = _completeness_gaps(r)
        if missing:
            gaps.append({"auditId": r.get("auditId"), "action": r.get("action"), "missing": missing})
    return {"totalHighRisk": len(high_risk_rows), "gapCount": len(gaps), "gaps": gaps}


def get_evidence(*, action: str | None = None, operator: str | None = None,
                 date_from: str | None = None, date_to: str | None = None,
                 page: int = 1, page_size: int = 50) -> dict:
    """只读证据查询，复用既有 db_service.audit_query（真实数据源，不重复实现）。"""
    from app.services import db_service

    rows, total = db_service.audit_query(page, page_size, action, operator, date_from, date_to)
    completeness = evaluate_evidence_completeness(rows)
    return {"items": rows, "total": total, "page": page, "pageSize": page_size,
           "completeness": completeness}


def _allowed_action_prefixes(patterns: set[str]) -> set[str] | None:
    """从一组有效权限模式反推"这个操作者能看哪些模块前缀的审计"。

    返回 None = 无限制（持有 audit.* 或 * 全量审计权）；
    返回空集合 = 完全没有任何审计可见权限（调用方应该拒绝）；
    返回非空集合 = 只能看这些模块前缀（如 systemAdmin、campusService）。
    """
    if "*" in patterns or "audit.*" in patterns:
        return None
    prefixes = set()
    for p in patterns:
        if p.endswith(".audit.view") or p.endswith(".audit.*"):
            prefixes.add(p.split(".")[0])
    return prefixes


def create_evidence_pack_job(user: dict, body: dict) -> dict:
    """登记一次证据包导出任务；范围快照严格按操作者当前有效权限收敛，
    不是"查询参数里想要多少就给多少"（PLAT09-T03 同类思路的证据包版本）。"""
    from app.core.permissions import get_effective_permission_patterns
    from app.models.data_exchange import ExportJob
    from app.services.db_service import session

    patterns = set(get_effective_permission_patterns(user))
    allowed_prefixes = _allowed_action_prefixes(patterns)
    if allowed_prefixes is not None and not allowed_prefixes:
        raise AppException("NO_PERMISSION", "当前角色没有任何审计查看权限，无法导出证据包", http_status=403)

    requested_action = str(body.get("action") or "").strip() or None
    # action 字段实际存的是 LOGIN/EXPORT 这类扁平动作码，不是 a.b.c 形式；
    # 真正按模块前缀收敛可见范围放在生成阶段按 resource 前缀过滤，
    # 这里只登记这次导出被允许覆盖哪些前缀（快照本身就是范围约束的证据）。
    scope_snapshot = {
        "tenantId": str(_tid()),
        "actionPrefixAllowlist": sorted(allowed_prefixes) if allowed_prefixes is not None else None,
        "actionFilter": requested_action,
        "dateFrom": body.get("dateFrom"),
        "dateTo": body.get("dateTo"),
        "generatedAt": datetime.utcnow().isoformat(),
    }

    actor_raw = str((user or {}).get("userId") or "").removeprefix("db-")
    actor_id = int(actor_raw) if actor_raw.isdigit() else None

    with session() as db:
        job = ExportJob(
            tenant_id=_tid(), module_code="systemAdmin", export_type="AUDIT_EVIDENCE_PACK",
            purpose=body.get("purpose") or "安全审计证据导出",
            filter_snapshot_json=body, data_scope_snapshot_json=scope_snapshot,
            status="CREATED", operator_id=actor_id)
        db.add(job)
        db.commit()
        return {
            "jobId": str(job.id), "status": job.status, "scopeSnapshot": scope_snapshot,
        }


def get_evidence_pack_scope(job_id: int) -> dict:
    from app.models.data_exchange import ExportJob
    from app.services.db_service import session

    with session() as db:
        job = db.get(ExportJob, int(job_id))
        if not job or job.is_deleted or job.tenant_id != _tid():
            raise AppException("DATA_NOT_FOUND", "证据包任务不存在", http_status=404)
        return {"jobId": str(job.id), "status": job.status,
               "scopeSnapshot": job.data_scope_snapshot_json,
               "filterSnapshot": job.filter_snapshot_json}


def governance_overview() -> dict:
    """首屏结论：登录风险、高危变更、敏感下载、权限激活、紧急访问和审计缺口。

    大部分维度（登录风险/敏感下载/权限激活/紧急访问）依赖各自模块自己的
    审计事件分类，这里只统一读 t_security_audit_log 的 action 前缀做粗分类，
    不重复实现各模块自己的风险判定逻辑。"""
    from app.services import db_service

    recent, total = db_service.audit_query(1, 500)
    completeness = evaluate_evidence_completeness(recent)
    login_risk = sum(1 for r in recent if "LOGIN" in (r.get("action") or "").upper()
                     and r.get("result") in ("FAIL", "DENIED"))
    sensitive_download = sum(1 for r in recent if "DOWNLOAD" in (r.get("action") or "").upper()
                             or "SENSITIVE" in (r.get("action") or "").upper())
    permission_activation = sum(1 for r in recent if "ACTIVATE" in (r.get("action") or "").upper()
                                or "ELEVATION" in (r.get("action") or "").upper())
    emergency_access = sum(1 for r in recent if "SUPPORT_SESSION" in (r.get("action") or "").upper()
                           or "ELEVATION" in (r.get("action") or "").upper())
    return {
        "totalRecent": total, "loginRiskCount": login_risk,
        "highRiskChangeCount": completeness["totalHighRisk"],
        "sensitiveDownloadCount": sensitive_download,
        "permissionActivationCount": permission_activation,
        "emergencyAccessCount": emergency_access,
        "auditGapCount": completeness["gapCount"], "auditGaps": completeness["gaps"][:20],
    }
