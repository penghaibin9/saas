"""PLAT-02 tenant lifecycle authority and tenant-360 projection.

The relational tenant row is the hard safety state.  Commercial lifecycle data
remains in TENANT_META until the later data migration, but every read now passes
through this resolver so disagreement is explicit and write paths are optimistic
locked rather than last-write-wins.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker

_META_STATES = {"trial", "active", "expired", "disabled", "readonly", "archived", "provisioning"}
_ROW_STATES = {"PROVISIONING", "ACTIVE", "SUSPENDED", "ARCHIVED"}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


def effective_state_from_records(
    *,
    row_status: str | None,
    meta: dict | None,
    now: datetime | None = None,
    strict: bool = True,
) -> dict:
    now = now or datetime.utcnow()
    row = str(row_status or "").upper()
    payload = dict(meta or {})
    meta_status = str(payload.get("status") or "").lower()
    errors: list[str] = []
    if row not in _ROW_STATES:
        errors.append("UNKNOWN_TENANT_ROW_STATUS")
    if meta_status and meta_status not in _META_STATES:
        errors.append("UNKNOWN_TENANT_META_STATUS")
    if strict and errors:
        raise AppException(
            "TENANT_STATE_UNRESOLVED",
            "租户有效状态无法确定，已按安全策略拒绝",
            http_status=409,
            details={"errors": errors, "rowStatus": row, "metaStatus": meta_status},
        )

    # Hard safety states always win over mutable commercial metadata.
    if errors:
        effective = "unresolved"
    elif row == "ARCHIVED":
        effective = "archived"
    elif row == "SUSPENDED":
        effective = "disabled"
    elif row == "PROVISIONING":
        effective = "provisioning"
    else:
        effective = meta_status or ("active" if row == "ACTIVE" else "disabled")
        expire_at = payload.get("expireAt")
        if effective in {"trial", "active"} and expire_at:
            try:
                if datetime.fromisoformat(str(expire_at).replace("Z", "+00:00")).replace(tzinfo=None) <= now:
                    effective = "expired"
            except (TypeError, ValueError):
                if strict:
                    raise AppException(
                        "TENANT_STATE_UNRESOLVED",
                        "租户到期时间格式无效，已按安全策略拒绝",
                        http_status=409,
                    )
                errors.append("INVALID_EXPIRE_AT")

    expected_meta_for_row = {
        "SUSPENDED": "disabled",
        "ARCHIVED": "archived",
        "PROVISIONING": "provisioning",
    }.get(row)
    mismatch = bool(
        (expected_meta_for_row and meta_status and meta_status != expected_meta_for_row)
        or (row == "ACTIVE" and meta_status == "disabled")
    )
    return {
        "effectiveStatus": effective,
        "rowStatus": row or None,
        "metaStatus": meta_status or None,
        "mismatch": mismatch,
        "errors": errors,
        "readonly": effective in {"expired", "readonly", "archived"},
        "writable": effective in {"trial", "active"},
        "expireAt": _iso(payload.get("expireAt")),
    }


def _meta_row(db, tenant_id: int, *, lock: bool = False):
    from app.models import PlatformConfig

    query = select(PlatformConfig).where(
        PlatformConfig.tenant_id == tenant_id,
        PlatformConfig.config_type == "TENANT_META",
        PlatformConfig.config_key == "-",
        PlatformConfig.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    return db.scalars(query).first()


def _version(tenant, meta_row) -> int:
    return max(int(getattr(tenant, "version", 1) or 1), int(getattr(meta_row, "version", 1) or 1))


def get_effective_state(tenant_id: int, *, strict: bool = True, db=None) -> dict:
    from app.models import Tenant

    owns = db is None
    working = db or get_sessionmaker()()
    try:
        tenant = working.get(Tenant, int(tenant_id))
        if not tenant or tenant.is_deleted:
            raise not_found("租户不存在")
        meta_row = _meta_row(working, int(tenant_id))
        if strict and meta_row is None:
            raise AppException("TENANT_STATE_UNRESOLVED", "租户生命周期配置缺失", http_status=409)
        result = effective_state_from_records(
            row_status=tenant.status,
            meta=dict(meta_row.config_json or {}) if meta_row else {},
            strict=strict,
        )
        result.update({
            "tenantId": str(tenant.id),
            "tenantCode": tenant.tenant_code,
            "tenantName": tenant.school_name,
            "version": _version(tenant, meta_row),
        })
        return result
    finally:
        if owns:
            working.close()


def _storage_projection(db, tenant_id: int) -> dict:
    from app.models.file import FileObject, TenantStorageQuota
    from app.models.file_quota import FileStorageQuotaReservation

    actual = int(db.scalar(select(func.coalesce(func.sum(FileObject.size_bytes), 0)).where(
        FileObject.tenant_id == tenant_id,
        FileObject.is_deleted.is_(False),
    )) or 0)
    held = int(db.scalar(select(func.coalesce(func.sum(FileStorageQuotaReservation.reserved_bytes), 0)).where(
        FileStorageQuotaReservation.tenant_id == tenant_id,
        FileStorageQuotaReservation.status == "HELD",
        FileStorageQuotaReservation.expires_at > datetime.utcnow(),
        FileStorageQuotaReservation.is_deleted.is_(False),
    )) or 0)
    school_quota = db.scalars(select(TenantStorageQuota).where(
        TenantStorageQuota.tenant_id == tenant_id,
        TenantStorageQuota.is_deleted.is_(False),
    )).first()
    return {
        "fileObjectBytes": actual,
        "heldReservationBytes": held,
        "actualOccupancyBytes": actual + held,
        "schoolGovernanceQuotaBytes": int(school_quota.total_quota_bytes) if school_quota else None,
        "schoolQuotaVersion": int(school_quota.version) if school_quota else None,
    }


def tenant_360(tenant_id: int) -> dict:
    from app.models import PlatformConfig, Tenant
    from app.services import platform_service
    from app.services.entitlement_reconciliation_service import commercial_storage_limit_bytes

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if not tenant or tenant.is_deleted:
            raise not_found("租户不存在")
        meta_row = _meta_row(db, int(tenant_id))
        meta = dict(meta_row.config_json or {}) if meta_row else {}
        state = effective_state_from_records(row_status=tenant.status, meta=meta, strict=True)
        package = platform_service.get_package(str(meta.get("packageCode") or "trial"))
        mismatch_rows = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == int(tenant_id),
            PlatformConfig.config_type.in_(("FEATURES", "TENANT_META")),
            PlatformConfig.is_deleted.is_(False),
        )).all()
        storage = _storage_projection(db, int(tenant_id))
        commercial = commercial_storage_limit_bytes(int(tenant_id), db=db, meta=meta, package=package)
        return {
            "tenantId": str(tenant.id),
            "tenantCode": tenant.tenant_code,
            "tenantName": tenant.school_name,
            "version": _version(tenant, meta_row),
            "effectiveState": state,
            "commercial": {
                "packageCode": package.get("packageCode"),
                "expireAt": meta.get("expireAt"),
                "commercialStorageLimitBytes": commercial,
            },
            "storage": {**storage, "commercialStorageLimitBytes": commercial},
            "configurationEvidence": [
                {"type": row.config_type, "key": row.config_key, "version": row.version}
                for row in mismatch_rows
            ],
        }
    finally:
        db.close()


def preview_transition(tenant_id: int, action: str, payload: dict | None = None) -> dict:
    current = get_effective_state(tenant_id, strict=True)
    data = dict(payload or {})
    normalized = str(action or "").strip().lower()
    target = {
        "enable": "active",
        "disable": "disabled",
        "expire": "expired",
        "convert-to-paid": "active",
        "change-package": current["effectiveStatus"],
        "quota": current["effectiveStatus"],
        "extend-trial": "trial" if current["effectiveStatus"] != "active" else "active",
    }.get(normalized)
    if target is None:
        raise AppException("VALIDATION_ERROR", "不支持的租户状态操作")
    warnings: list[str] = []
    if normalized == "disable":
        warnings.append("该校所有交互式登录和写操作将立即拒绝")
    if normalized == "expire":
        warnings.append("历史数据保留可查，但业务写入转为只读")
    if normalized == "change-package":
        warnings.append("降配不会静默删除文件；超额项将进入对账异常")
    if normalized == "extend-trial":
        warnings.append("延期只改变商业有效期，不会改变学校数据或文件")
    return {
        "tenantId": str(tenant_id),
        "action": normalized,
        "fromStatus": current["effectiveStatus"],
        "toStatus": target,
        "expectedVersion": current["version"],
        "warnings": warnings,
        "requested": data,
    }


def apply_transition(
    tenant_id: int,
    action: str,
    *,
    reason: str,
    expected_version: int,
    payload: dict | None = None,
) -> dict:
    from app.models import PlatformConfig, Tenant
    from app.services import platform_service
    from app.services.auth_service_db import invalidate_tenant_subject_caches

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "变更原因至少5个字符")
    normalized = str(action or "").strip().lower()
    data = dict(payload or {})
    db = get_sessionmaker()()
    try:
        tenant = db.scalars(select(Tenant).where(
            Tenant.id == int(tenant_id), Tenant.is_deleted.is_(False)
        ).with_for_update()).first()
        if not tenant:
            raise not_found("租户不存在")
        meta_row = _meta_row(db, int(tenant_id), lock=True)
        if meta_row is None:
            meta_row = PlatformConfig(
                tenant_id=int(tenant_id), config_type="TENANT_META", config_key="-",
                config_json={}, enabled=True,
            )
            db.add(meta_row)
            db.flush()
        current_version = _version(tenant, meta_row)
        if int(expected_version) != current_version:
            raise AppException(
                "DATA_CONFLICT",
                "租户状态已被其他操作更新，请刷新后重试",
                http_status=409,
                details={"expectedVersion": expected_version, "currentVersion": current_version},
            )
        meta = dict(meta_row.config_json or {})
        before = effective_state_from_records(row_status=tenant.status, meta=meta, strict=True)
        now = datetime.utcnow()
        if normalized == "enable":
            tenant.status = "ACTIVE"
            meta["status"] = "active"
        elif normalized == "disable":
            tenant.status = "SUSPENDED"
            meta["status"] = "disabled"
        elif normalized == "expire":
            tenant.status = "ACTIVE"
            meta.update({"status": "expired", "expireAt": (now - timedelta(seconds=1)).isoformat(timespec="seconds")})
        elif normalized == "convert-to-paid":
            package = platform_service.get_package(str(data.get("packageCode") or "standard"))
            days = int(data.get("durationDays") or package["durationDays"])
            tenant.status = "ACTIVE"
            meta.update({
                "status": "active",
                "packageCode": package["packageCode"],
                "expireAt": (now + timedelta(days=days)).isoformat(timespec="seconds"),
            })
        elif normalized == "change-package":
            code = str(data.get("packageCode") or "")
            package = platform_service.get_package(code)
            if package.get("packageCode") != code:
                raise AppException("VALIDATION_ERROR", "packageCode 不存在")
            meta["packageCode"] = code
        elif normalized == "quota":
            for key in ("maxStudents", "maxUsers", "storageLimitMb"):
                if key in data:
                    value = int(data[key])
                    if value <= 0:
                        raise AppException("VALIDATION_ERROR", f"{key} 必须为正整数")
                    meta[key] = value
        elif normalized == "extend-trial":
            days = int(data.get("days") or 7)
            if not 1 <= days <= 365:
                raise AppException("VALIDATION_ERROR", "延长天数需在1-365之间")
            base = meta.get("expireAt") or meta.get("trialEndAt")
            try:
                start = max(datetime.fromisoformat(str(base)).replace(tzinfo=None), now) if base else now
            except ValueError:
                raise AppException("TENANT_STATE_UNRESOLVED", "租户到期时间格式无效", http_status=409) from None
            new_end = (start + timedelta(days=days)).isoformat(timespec="seconds")
            meta.update({
                "trialEndAt": new_end,
                "expireAt": new_end,
                "status": "active" if before["effectiveStatus"] == "active" else "trial",
            })
            tenant.status = "ACTIVE"
        else:
            raise AppException("VALIDATION_ERROR", "不支持的租户状态操作")
        meta["lastLifecycleReason"] = reason_text[:1000]
        meta["lastLifecycleAt"] = now.isoformat(timespec="seconds")
        meta_row.config_json = meta
        meta_row.version = int(meta_row.version or 1) + 1
        tenant.version = int(tenant.version or 1) + 1
        db.commit()
        invalidate_tenant_subject_caches(int(tenant_id))
        after = get_effective_state(int(tenant_id), strict=True)
        refreshed_meta = platform_service.tenant_meta(int(tenant_id))
        return {
            "tenantId": str(tenant_id),
            "action": normalized,
            "reason": reason_text,
            "before": before,
            "after": after,
            "version": after["version"],
            "status": after["effectiveStatus"],
            "packageCode": refreshed_meta.get("packageCode"),
            "expireAt": refreshed_meta.get("expireAt"),
            "maxStudents": refreshed_meta.get("maxStudents"),
            "maxUsers": refreshed_meta.get("maxUsers"),
            "storageLimitMb": refreshed_meta.get("storageLimitMb"),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
