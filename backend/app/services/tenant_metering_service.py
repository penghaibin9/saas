"""PLAT-13 租户用量、容量、成本快照。

每天的用量数字全部来自既有真实表的实时聚合（SecurityAuditLog/FileObject/
User/StudentProfile），这里只是按天落一条快照供趋势查询，不新建任何一套
计数口径。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from app.db.session import get_sessionmaker
from app.models.tenant_metering import TenantUsageSnapshot


def _session():
    return get_sessionmaker()()


def _snapshot_dto(row: TenantUsageSnapshot) -> dict:
    return {
        "id": str(row.id), "tenantId": str(row.tenant_id),
        "snapshotDate": row.snapshot_date.isoformat(),
        "auditEventCount": row.audit_event_count, "fileUploadBytes": row.file_upload_bytes,
        "storageTotalBytes": row.storage_total_bytes,
        "studentCount": row.student_count, "userCount": row.user_count,
    }


def _real_usage_for_tenant(db, tenant_id: int, day: date) -> dict:
    from app.models import SecurityAuditLog, StudentProfile, User
    from app.models.file import FileObject

    day_start = datetime.combine(day, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    audit_event_count = db.scalar(select(func.count()).select_from(SecurityAuditLog).where(
        SecurityAuditLog.tenant_id == tenant_id,
        SecurityAuditLog.created_at >= day_start, SecurityAuditLog.created_at < day_end)) or 0
    file_upload_bytes = db.scalar(select(func.coalesce(func.sum(FileObject.size_bytes), 0)).where(
        FileObject.tenant_id == tenant_id, FileObject.is_deleted.is_(False),
        FileObject.created_at >= day_start, FileObject.created_at < day_end)) or 0
    storage_total_bytes = db.scalar(select(func.coalesce(func.sum(FileObject.size_bytes), 0)).where(
        FileObject.tenant_id == tenant_id, FileObject.is_deleted.is_(False))) or 0
    student_count = db.scalar(select(func.count()).select_from(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id, StudentProfile.is_deleted.is_(False))) or 0
    user_count = db.scalar(select(func.count()).select_from(User).where(
        User.tenant_id == tenant_id, User.is_deleted.is_(False))) or 0
    return {
        "auditEventCount": int(audit_event_count), "fileUploadBytes": int(file_upload_bytes),
        "storageTotalBytes": int(storage_total_bytes), "studentCount": int(student_count),
        "userCount": int(user_count),
    }


def capture_daily_snapshot(tenant_id: int, *, snapshot_date: date | None = None) -> dict:
    """幂等：同一租户同一天重复调用只更新数字，不产生第二条快照。"""
    day = snapshot_date or datetime.utcnow().date()
    with _session() as db:
        usage = _real_usage_for_tenant(db, int(tenant_id), day)
        row = db.scalars(select(TenantUsageSnapshot).where(
            TenantUsageSnapshot.tenant_id == int(tenant_id),
            TenantUsageSnapshot.snapshot_date == day)).first()
        if row is None:
            row = TenantUsageSnapshot(tenant_id=int(tenant_id), snapshot_date=day)
            db.add(row)
        row.audit_event_count = usage["auditEventCount"]
        row.file_upload_bytes = usage["fileUploadBytes"]
        row.storage_total_bytes = usage["storageTotalBytes"]
        row.student_count = usage["studentCount"]
        row.user_count = usage["userCount"]
        db.commit()
        db.refresh(row)
        return _snapshot_dto(row)


def capture_all_tenants(*, snapshot_date: date | None = None) -> dict:
    from sqlalchemy import select as sa_select

    from app.models import Tenant

    db = _session()
    try:
        tenants = db.scalars(sa_select(Tenant).where(Tenant.is_deleted.is_(False))).all()
    finally:
        db.close()
    for t in tenants:
        capture_daily_snapshot(t.id, snapshot_date=snapshot_date)
    return {"tenantCount": len(tenants), "snapshotDate": (snapshot_date or datetime.utcnow().date()).isoformat()}


def list_snapshots(tenant_id: int, *, days: int = 30) -> list[dict]:
    since = datetime.utcnow().date() - timedelta(days=days)
    with _session() as db:
        rows = db.scalars(select(TenantUsageSnapshot).where(
            TenantUsageSnapshot.tenant_id == int(tenant_id),
            TenantUsageSnapshot.snapshot_date >= since
        ).order_by(TenantUsageSnapshot.snapshot_date.asc())).all()
        return [_snapshot_dto(r) for r in rows]


def latest_snapshot(tenant_id: int) -> dict | None:
    with _session() as db:
        row = db.scalars(select(TenantUsageSnapshot).where(
            TenantUsageSnapshot.tenant_id == int(tenant_id)
        ).order_by(TenantUsageSnapshot.snapshot_date.desc())).first()
        return _snapshot_dto(row) if row else None


def governance_overview() -> dict:
    """跨租户用量总览：最新一条快照按存储总量排序，找出用量最大的学校。"""
    with _session() as db:
        latest_per_tenant: dict[int, TenantUsageSnapshot] = {}
        rows = db.scalars(select(TenantUsageSnapshot).order_by(
            TenantUsageSnapshot.tenant_id, TenantUsageSnapshot.snapshot_date.desc())).all()
        for r in rows:
            if r.tenant_id not in latest_per_tenant:
                latest_per_tenant[r.tenant_id] = r
    top_by_storage = sorted(latest_per_tenant.values(), key=lambda r: -r.storage_total_bytes)[:10]
    top_by_audit = sorted(latest_per_tenant.values(), key=lambda r: -r.audit_event_count)[:10]
    return {
        "tenantsWithSnapshot": len(latest_per_tenant),
        "topByStorage": [_snapshot_dto(r) for r in top_by_storage],
        "topByAuditVolume": [_snapshot_dto(r) for r in top_by_audit],
    }
