"""Code-first authority projections for the platform control plane.

This module is deliberately outside the byte-frozen platform bundle.  It owns
read-only authority projections used by exact route replacements during W1-W4.
Legacy PlatformConfig rows are evidence/compatibility inputs, not a license for
new side writes.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.services import platform_defaults as D


def config_snapshot(tenant_id: int, config_type: str, key: str = "-") -> dict:
    """Return one PlatformConfig payload together with its optimistic-lock version."""
    from app.models import PlatformConfig

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == int(tenant_id),
            PlatformConfig.config_type == str(config_type),
            PlatformConfig.config_key == str(key),
            PlatformConfig.is_deleted.is_(False),
        )).first()
        return {
            "exists": row is not None,
            "payload": dict(row.config_json or {}) if row else {},
            "version": int(row.version or 1) if row else 0,
        }
    finally:
        db.close()


def features_projection(tenant_id: int) -> dict:
    """Expose commercial entitlement plus any grandfathered legacy override.

    W1 freezes the legacy FEATURES writer. Existing rows remain readable and
    visible in reconciliation so an operator can migrate/resolve them without
    destroying evidence. New normal entitlement changes must come from a paid
    order (packageCode on TENANT_META); controlled exceptions stay explicit.
    """
    from app.services import platform_service

    tenant = platform_service.get_tenant(int(tenant_id))
    meta = platform_service.tenant_meta(int(tenant_id))
    package = platform_service.get_package(str(meta.get("packageCode") or "professional"))
    package_merged = {**D.DEFAULT_FEATURES, **(package.get("features") or {})}
    package_features = {key: bool(package_merged.get(key, False)) for key in D.FEATURE_KEYS}
    legacy = config_snapshot(int(tenant_id), "FEATURES")
    effective = platform_service.effective_features(int(tenant_id))
    drift = {
        key: {"package": package_features.get(key, False), "legacy": bool(value)}
        for key, value in legacy["payload"].items()
        if key in D.FEATURE_KEYS and bool(value) != bool(package_features.get(key, False))
    }
    if legacy["payload"]:
        authority_source = "LEGACY_OVERRIDE_READ_ONLY"
    elif meta.get("lastCommercialOrderNo"):
        authority_source = "PAID_ORDER"
    elif str(meta.get("lastCommercialAuthority") or "").upper() == "CONTROLLED_EXCEPTION":
        authority_source = "CONTROLLED_EXCEPTION"
    else:
        authority_source = "PACKAGE"
    return {
        "tenantId": str(tenant_id),
        "tenantName": tenant.get("tenantName"),
        "packageCode": package.get("packageCode"),
        "features": effective,
        "packageFeatures": package_features,
        "authoritySource": authority_source,
        "commercialOrderNo": meta.get("lastCommercialOrderNo") or None,
        "legacyOverride": legacy["payload"],
        "legacyOverrideVersion": legacy["version"],
        "legacyOverrideReadOnly": bool(legacy["payload"]),
        "legacyDrift": drift,
        "repairRequired": bool(drift),
    }
