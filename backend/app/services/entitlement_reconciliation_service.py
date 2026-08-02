"""PLAT-03 commercial entitlement, quota and consumption reconciliation."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

_MIB = 1024 * 1024
_LEGACY_PACKAGE_CODE = "professional"


def commercial_storage_limit_bytes(
    tenant_id: int,
    *,
    db=None,
    meta: dict | None = None,
    package: dict | None = None,
) -> int:
    from app.services import platform_service

    payload = dict(meta if meta is not None else platform_service.tenant_meta(int(tenant_id)))
    package_code = str(payload.get("packageCode") or _LEGACY_PACKAGE_CODE)
    pkg = dict(package if package is not None else platform_service.get_package(package_code))
    # Tenant commercial override may lower/raise the package ceiling, but it is
    # still platform-owned. School governance quota is a separate lower layer.
    # Pre-PLAT-02 tenants had no TENANT_META and historically inherited the
    # professional capability set; keep their commercial ceiling consistent
    # instead of silently downgrading them to the 512 MiB trial package.
    mb = int(payload.get("storageLimitMb") or pkg.get("storageLimitMb") or 0)
    return max(0, mb) * _MIB


def reconcile_snapshot(snapshot: dict[str, Any]) -> dict:
    commercial = max(0, int(snapshot.get("commercialStorageLimitBytes") or 0))
    school = snapshot.get("schoolGovernanceQuotaBytes")
    school = int(school) if school is not None else None
    file_bytes = max(0, int(snapshot.get("fileObjectBytes") or 0))
    held = max(0, int(snapshot.get("heldReservationBytes") or 0))
    actual = file_bytes + held
    violations: list[dict] = []
    if commercial and school is not None and school > commercial:
        violations.append({
            "code": "SCHOOL_QUOTA_EXCEEDS_COMMERCIAL",
            "severity": "P1",
            "commercialBytes": commercial,
            "schoolQuotaBytes": school,
        })
    if commercial and actual > commercial:
        violations.append({
            "code": "ACTUAL_USAGE_EXCEEDS_COMMERCIAL",
            "severity": "P1",
            "commercialBytes": commercial,
            "actualBytes": actual,
        })
    for item in snapshot.get("moduleUsage") or []:
        if int(item.get("bytes") or 0) > 0 and not bool(item.get("entitled", False)):
            violations.append({
                "code": "UNAUTHORIZED_MODULE_USAGE",
                "severity": "P1",
                "moduleCode": item.get("moduleCode"),
                "bytes": int(item.get("bytes") or 0),
            })
    if bool(snapshot.get("paidOrder")) and not bool(snapshot.get("provisioned")):
        violations.append({
            "code": "PAID_ORDER_NOT_PROVISIONED",
            "severity": "P1",
            "repairable": True,
        })
    return {
        **snapshot,
        "actualConsumptionBytes": actual,
        "healthy": not violations,
        "violations": violations,
        "repairTaskRequired": bool(violations),
    }


def _module_from_biz(value: str | None) -> str:
    biz = str(value or "").upper()
    for prefix, module in (
        ("GRADUATION", "graduation"),
        ("INTERNSHIP", "internship"),
        ("AFFAIRS", "studentAffairs"),
        ("ACADEMIC", "academicAffairs"),
        ("ORIENTATION", "orientation"),
    ):
        if biz.startswith(prefix):
            return module
    return "shared"


def reconcile_tenant(tenant_id: int) -> dict:
    from app.models import PlatformOrder, Tenant
    from app.models.file import FileObject, TenantStorageQuota
    from app.models.file_quota import FileStorageQuotaReservation
    from app.services import module_access_service, platform_service

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if not tenant or tenant.is_deleted:
            raise AppException("NOT_FOUND", "租户不存在", http_status=404)
        meta = platform_service.tenant_meta(int(tenant_id))
        package = platform_service.get_package(str(meta.get("packageCode") or _LEGACY_PACKAGE_CODE))
        commercial = commercial_storage_limit_bytes(int(tenant_id), db=db, meta=meta, package=package)
        quota = db.scalars(select(TenantStorageQuota).where(
            TenantStorageQuota.tenant_id == int(tenant_id),
            TenantStorageQuota.is_deleted.is_(False),
        )).first()
        file_bytes = int(db.scalar(select(func.coalesce(func.sum(FileObject.size_bytes), 0)).where(
            FileObject.tenant_id == int(tenant_id),
            FileObject.is_deleted.is_(False),
        )) or 0)
        held = int(db.scalar(select(func.coalesce(func.sum(FileStorageQuotaReservation.reserved_bytes), 0)).where(
            FileStorageQuotaReservation.tenant_id == int(tenant_id),
            FileStorageQuotaReservation.status == "HELD",
            FileStorageQuotaReservation.expires_at > datetime.utcnow(),
            FileStorageQuotaReservation.is_deleted.is_(False),
        )) or 0)
        grouped = db.execute(select(
            FileObject.biz_type,
            func.coalesce(func.sum(FileObject.size_bytes), 0),
        ).where(
            FileObject.tenant_id == int(tenant_id), FileObject.is_deleted.is_(False),
        ).group_by(FileObject.biz_type)).all()
        module_usage = []
        for biz_type, amount in grouped:
            module = _module_from_biz(biz_type)
            entitled = True
            if module != "shared":
                try:
                    entitled = bool(module_access_service.module_access_state(int(tenant_id), module)["entitled"])
                except Exception:
                    entitled = False
            module_usage.append({
                "moduleCode": module,
                "bizType": biz_type,
                "bytes": int(amount or 0),
                "entitled": entitled,
            })
        paid_order = db.scalars(select(PlatformOrder).where(
            PlatformOrder.tenant_id == int(tenant_id),
            PlatformOrder.status.in_(("paid", "active", "PAID", "ACTIVE")),
            PlatformOrder.is_deleted.is_(False),
        ).order_by(PlatformOrder.id.desc())).first()
        snapshot = {
            "tenantId": str(tenant.id),
            "tenantCode": tenant.tenant_code,
            "tenantName": tenant.school_name,
            "packageCode": package.get("packageCode"),
            "commercialStorageLimitBytes": commercial,
            "schoolGovernanceQuotaBytes": int(quota.total_quota_bytes) if quota else None,
            "fileObjectBytes": file_bytes,
            "heldReservationBytes": held,
            "moduleUsage": module_usage,
            "paidOrder": bool(paid_order),
            "provisioned": str(tenant.status).upper() in {"ACTIVE", "SUSPENDED"},
        }
        return reconcile_snapshot(snapshot)
    finally:
        db.close()


def list_reconciliations(tenant_id: int | None = None) -> list[dict]:
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        ids = [int(tenant_id)] if tenant_id else [
            int(value) for value in db.scalars(select(Tenant.id).where(Tenant.is_deleted.is_(False))).all()
        ]
    finally:
        db.close()
    return [reconcile_tenant(value) for value in ids]


def downgrade_impact_preview(*, current_limit_bytes: int, target_limit_bytes: int, actual_bytes: int) -> dict:
    current = max(0, int(current_limit_bytes))
    target = max(0, int(target_limit_bytes))
    actual = max(0, int(actual_bytes))
    return {
        "currentLimitBytes": current,
        "targetLimitBytes": target,
        "actualBytes": actual,
        "overageBytes": max(0, actual - target),
        "willDeleteFiles": False,
        "requiresRepairPlan": actual > target,
    }
