"""Tenant brand authority shared by school system management and platform read projection.

`t_tenant_brand_config` is the single runtime UI brand authority. Historical
`PlatformConfig(BRAND)` rows are exposed only as reconciliation evidence.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.session import get_sessionmaker

_BRAND_LOCKED_NAME = "高校学生全生命周期管理平台"
_EDITABLE = ("schoolShortName", "brandColor", "loginSlogan", "watermarkText", "watermarkDensity", "footerText")


def _required_version(value) -> int:
    from app.core.exceptions import AppException

    if value in (None, ""):
        raise AppException("VALIDATION_ERROR", "品牌变更必须提供 expectedVersion", http_status=422)
    try:
        version = int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "品牌 expectedVersion 必须为整数", http_status=422) from None
    if version < 0:
        raise AppException("VALIDATION_ERROR", "品牌 expectedVersion 不能为负数", http_status=422)
    return version


def _required_reason(value) -> str:
    from app.core.exceptions import AppException

    reason = str(value or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "品牌变更原因至少5个字符", http_status=422)
    return reason


def _legacy_snapshot(db, tenant_id: int) -> dict:
    from app.models import PlatformConfig

    row = db.scalars(select(PlatformConfig).where(
        PlatformConfig.tenant_id == int(tenant_id),
        PlatformConfig.config_type == "BRAND",
        PlatformConfig.config_key == "-",
        PlatformConfig.is_deleted.is_(False),
    )).first()
    return {
        "payload": dict(row.config_json or {}) if row else {},
        "version": int(row.version or 1) if row else 0,
    }


def _form(db, tenant_id: int) -> dict:
    from app.models import Tenant, TenantBrandConfig

    row = db.scalars(select(TenantBrandConfig).where(
        TenantBrandConfig.tenant_id == int(tenant_id),
        TenantBrandConfig.is_deleted.is_(False),
    )).first()
    tenant = db.get(Tenant, int(tenant_id))
    extra = row.config_json if row is not None and isinstance(row.config_json, dict) else {}
    return {
        "schoolName": (tenant.school_name if tenant else "") or "",
        "platformDisplayName": _BRAND_LOCKED_NAME,
        "schoolShortName": extra.get("schoolShortName", "") or (tenant.short_name if tenant else "") or "",
        "brandColor": (row.primary_color if row is not None else "") or "#2563EB",
        "loginSlogan": extra.get("loginSlogan", "") or (row.motto if row is not None else "") or "",
        "watermarkText": (row.watermark_text if row is not None else "") or "",
        "watermarkDensity": extra.get("watermarkDensity", "") or "适中",
        "footerText": extra.get("footerText", "") or "",
        "version": int(row.version or 0) if row is not None else 0,
    }


def brand_projection(tenant_id: int) -> dict:
    from app.core.exceptions import AppException
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if tenant is None or tenant.is_deleted:
            raise AppException("NOT_FOUND", "租户不存在", http_status=404)
        brand = _form(db, int(tenant_id))
        legacy = _legacy_snapshot(db, int(tenant_id))
        return {
            "tenantId": str(tenant_id),
            "authority": "TENANT_BRAND_CONFIG",
            "brand": brand,
            "version": brand["version"],
            "legacyOverride": legacy["payload"],
            "legacyOverrideVersion": legacy["version"],
            "legacyOverrideReadOnly": bool(legacy["payload"]),
            "repairRequired": bool(legacy["payload"]),
            "writeSurface": "/admin/system/config?tab=brand",
        }
    finally:
        db.close()


def update_school_brand(
    tenant_id: int, *, brand: dict, expected_version, reason: str, user: dict | None = None,
) -> dict:
    from app.core.exceptions import AppException
    from app.models import Tenant, TenantBrandConfig
    from app.services import audit_log

    version = _required_version(expected_version)
    reason_text = _required_reason(reason)
    patch = {key: str(value) for key, value in dict(brand or {}).items() if key in _EDITABLE and value is not None}
    if not patch:
        raise AppException("VALIDATION_ERROR", "没有可更新的品牌字段", http_status=422)

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if tenant is None or tenant.is_deleted:
            raise AppException("NOT_FOUND", "租户不存在", http_status=404)
        row = db.scalars(select(TenantBrandConfig).where(
            TenantBrandConfig.tenant_id == int(tenant_id),
            TenantBrandConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        current_version = int(row.version or 0) if row is not None else 0
        if version != current_version:
            raise AppException(
                "DATA_CONFLICT", "品牌配置已被其他管理员更新，请刷新后重试", http_status=409,
                details={"expectedVersion": version, "currentVersion": current_version},
            )
        before = _form(db, int(tenant_id))
        if row is None:
            row = TenantBrandConfig(tenant_id=int(tenant_id))
            db.add(row)
            db.flush()

        if "brandColor" in patch:
            row.primary_color = patch["brandColor"]
        if "watermarkText" in patch:
            row.watermark_text = patch["watermarkText"]
        extra = dict(row.config_json or {})
        for key in ("schoolShortName", "loginSlogan", "watermarkDensity", "footerText"):
            if key in patch:
                extra[key] = patch[key]
        row.config_json = extra
        row.version = current_version + 1

        audit_log.record_critical_in_session(
            db, "BRAND_CONFIG", "学校品牌配置",
            detail={
                "keys": sorted(patch),
                "reason": reason_text,
                "before": before,
                "after": patch,
                "expectedVersion": version,
                "currentVersion": int(row.version),
                "moduleCode": "systemAdmin",
            },
            tenant_id=int(tenant_id),
            resource_id=str(row.id),
        )
        db.commit()
        return _form(db, int(tenant_id))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def reset_school_brand(
    tenant_id: int, *, expected_version=None, reason: str, user: dict | None = None,
) -> dict:
    """Reset under a row lock; current UI may omit expectedVersion during transition."""
    from app.core.exceptions import AppException
    from app.models import TenantBrandConfig
    from app.services import audit_log

    reason_text = _required_reason(reason)
    requested = None if expected_version in (None, "") else _required_version(expected_version)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(TenantBrandConfig).where(
            TenantBrandConfig.tenant_id == int(tenant_id),
            TenantBrandConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        current_version = int(row.version or 0) if row is not None else 0
        if requested is not None and requested != current_version:
            raise AppException(
                "DATA_CONFLICT", "品牌配置已被其他管理员更新，请刷新后重试", http_status=409,
                details={"expectedVersion": requested, "currentVersion": current_version},
            )
        before = _form(db, int(tenant_id))
        if row is not None:
            row.primary_color = "#2563EB"
            row.watermark_text = ""
            extra = dict(row.config_json or {})
            for key in ("schoolShortName", "loginSlogan", "watermarkDensity", "footerText"):
                extra.pop(key, None)
            row.config_json = extra
            row.version = current_version + 1
            resource_id = str(row.id)
        else:
            resource_id = ""
        audit_log.record_critical_in_session(
            db, "BRAND_CONFIG_RESET", "学校品牌配置",
            detail={
                "reason": reason_text,
                "before": before,
                "expectedVersion": requested,
                "currentVersion": int(row.version or 0) if row is not None else 0,
                "moduleCode": "systemAdmin",
            },
            tenant_id=int(tenant_id),
            resource_id=resource_id,
        )
        db.commit()
        return _form(db, int(tenant_id))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def effective_brand(tenant_id: int) -> dict:
    """Compatibility projection for legacy platform_service callers."""
    projection = brand_projection(int(tenant_id))["brand"]
    return {
        "schoolName": projection["schoolName"],
        "platformName": projection["platformDisplayName"],
        "topBarName": projection["platformDisplayName"],
        "primaryColor": projection["brandColor"],
        "watermarkText": projection["watermarkText"],
        "copyrightText": projection["footerText"],
    }


def install_platform_service_adapter() -> None:
    from app.services import platform_service
    platform_service.effective_brand = effective_brand
