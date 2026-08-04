"""PLAT-13 公平使用：保护共享核心服务不被单个学校拖垮。

判定用量直接读 tenant_metering_service 当天真实快照，不重复统计。默认
配额是平台兜底值，学校可以被单独放宽/收紧（t_tenant_fair_use_limit）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.tenant_metering import TenantFairUseLimit, TenantFairUseViolation

DEFAULT_LIMITS = {
    "AUDIT_EVENTS_PER_DAY": 5000,
    "FILE_UPLOAD_BYTES_PER_DAY": 5 * 1024 * 1024 * 1024,  # 5 GiB/天
}
RESOURCE_CODES = tuple(DEFAULT_LIMITS.keys())


def _session():
    return get_sessionmaker()()


def _limit_dto(row: TenantFairUseLimit) -> dict:
    return {
        "id": str(row.id), "tenantId": str(row.tenant_id), "resourceCode": row.resource_code,
        "dailyLimit": row.daily_limit, "status": row.status, "version": int(row.version or 0),
    }


def get_effective_limit(tenant_id: int, resource_code: str) -> int:
    with _session() as db:
        row = db.scalars(select(TenantFairUseLimit).where(
            TenantFairUseLimit.tenant_id == int(tenant_id),
            TenantFairUseLimit.resource_code == resource_code,
            TenantFairUseLimit.is_deleted.is_(False))).first()
        if row is not None:
            return int(row.daily_limit)
    return DEFAULT_LIMITS.get(resource_code, 0)


def upsert_limit(tenant_id: int, *, resource_code: str, daily_limit: int) -> dict:
    if resource_code not in RESOURCE_CODES:
        raise AppException("VALIDATION_ERROR", f"不支持的资源类型：{resource_code}")
    if daily_limit <= 0:
        raise AppException("VALIDATION_ERROR", "配额必须大于0")
    with _session() as db:
        row = db.scalars(select(TenantFairUseLimit).where(
            TenantFairUseLimit.tenant_id == int(tenant_id),
            TenantFairUseLimit.resource_code == resource_code)).first()
        if row is None:
            row = TenantFairUseLimit(tenant_id=int(tenant_id), resource_code=resource_code,
                                     daily_limit=int(daily_limit), status="ACTIVE")
            db.add(row)
        else:
            row.daily_limit = int(daily_limit)
            row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return _limit_dto(row)


def evaluate_tenant(tenant_id: int) -> dict:
    """用今天的真实用量快照跟配额比，超出的记一条违规；不重复算用量。"""
    from app.services.tenant_metering_service import capture_daily_snapshot

    today = datetime.utcnow().date()
    snapshot = capture_daily_snapshot(int(tenant_id), snapshot_date=today)
    field_for_resource = {
        "AUDIT_EVENTS_PER_DAY": "auditEventCount",
        "FILE_UPLOAD_BYTES_PER_DAY": "fileUploadBytes",
    }
    violations: list[dict] = []
    with _session() as db:
        for resource_code, field in field_for_resource.items():
            limit_value = get_effective_limit(int(tenant_id), resource_code)
            actual_value = int(snapshot[field])
            if actual_value <= limit_value:
                continue
            existing = db.scalars(select(TenantFairUseViolation).where(
                TenantFairUseViolation.tenant_id == int(tenant_id),
                TenantFairUseViolation.resource_code == resource_code,
                TenantFairUseViolation.violation_date == today)).first()
            if existing is not None:
                existing.actual_value = actual_value
                existing.limit_value = limit_value
                row = existing
            else:
                row = TenantFairUseViolation(
                    tenant_id=int(tenant_id), resource_code=resource_code, violation_date=today,
                    actual_value=actual_value, limit_value=limit_value, action_taken="LOGGED")
                db.add(row)
            db.commit()
            violations.append({"resourceCode": resource_code, "actualValue": actual_value,
                               "limitValue": limit_value})
    return {"tenantId": str(tenant_id), "violations": violations, "withinLimits": not violations}


def list_violations(tenant_id: int | None = None, *, days: int = 7) -> list[dict]:
    from datetime import timedelta

    since = datetime.utcnow().date() - timedelta(days=days)
    with _session() as db:
        q = select(TenantFairUseViolation).where(TenantFairUseViolation.violation_date >= since)
        if tenant_id:
            q = q.where(TenantFairUseViolation.tenant_id == int(tenant_id))
        rows = db.scalars(q.order_by(TenantFairUseViolation.violation_date.desc())).all()
        return [{
            "id": str(r.id), "tenantId": str(r.tenant_id), "resourceCode": r.resource_code,
            "violationDate": r.violation_date.isoformat(), "actualValue": r.actual_value,
            "limitValue": r.limit_value, "actionTaken": r.action_taken,
        } for r in rows]


def governance_overview() -> dict:
    from datetime import timedelta

    today = datetime.utcnow().date()
    with _session() as db:
        today_violations = db.scalars(select(TenantFairUseViolation).where(
            TenantFairUseViolation.violation_date == today)).all()
        tenants_over_limit = {v.tenant_id for v in today_violations}
        since = today - timedelta(days=7)
        recent = db.scalars(select(TenantFairUseViolation).where(
            TenantFairUseViolation.violation_date >= since)).all()
        consecutive_by_tenant: dict[int, int] = {}
        for t in tenants_over_limit:
            days_hit = {v.violation_date for v in recent if v.tenant_id == t}
            consecutive_by_tenant[t] = len(days_hit)
        chronic_offenders = [{"tenantId": str(t), "violationDaysLast7": d}
                             for t, d in consecutive_by_tenant.items() if d >= 3]
    return {
        "tenantsOverLimitToday": len(tenants_over_limit),
        "chronicOffenders": sorted(chronic_offenders, key=lambda x: -x["violationDaysLast7"])[:10],
    }
