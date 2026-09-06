"""Commercial entitlement authority for W1 runtime cutover.

Legacy tenant ``PlatformConfig(FEATURES)`` rows are historical evidence only.
Runtime entitlement is derived from the tenant's materialized commercial package
(which is changed by the paid-order / controlled-exception lifecycle commands).
"""
from __future__ import annotations

import logging

from app.services import platform_defaults as D

_LOG = logging.getLogger("platform.commercial-entitlement")
_ORIGINAL_PRELOADED = None


def effective_features(tenant_id: int) -> dict[str, bool]:
    """Return package/order materialized entitlement; never merge legacy FEATURES."""
    from app.services import platform_service

    meta = platform_service.tenant_meta(int(tenant_id))
    package = platform_service.get_package(str(meta.get("packageCode") or "professional"))
    merged = {**D.DEFAULT_FEATURES, **(package.get("features") or {})}
    return {key: bool(merged.get(key, False)) for key in D.FEATURE_KEYS}


def feature_enabled(tenant_id: int, key: str) -> bool:
    """Fail-closed feature check over the commercial authority projection."""
    from app.core.module_registry import resolve_feature_key

    feature = resolve_feature_key(key) or (key if key in D.FEATURE_KEYS else None)
    if feature is None or feature not in D.FEATURE_KEYS:
        _LOG.warning("unknown feature denied tenant=%s key=%s", tenant_id, key)
        return False
    try:
        return bool(effective_features(int(tenant_id)).get(feature, False))
    except Exception:
        _LOG.exception("commercial entitlement read failed tenant=%s key=%s", tenant_id, key)
        return False


def authority_source(tenant_id: int) -> str:
    from app.services import platform_service

    meta = platform_service.tenant_meta(int(tenant_id))
    if meta.get("lastCommercialOrderNo"):
        return "PAID_ORDER"
    if str(meta.get("lastCommercialAuthority") or "").strip().upper() == "CONTROLLED_EXCEPTION":
        return "CONTROLLED_EXCEPTION"
    return "PACKAGE"


def legacy_override_snapshot(tenant_id: int) -> dict:
    """Read grandfathered FEATURES only for reconciliation; never for authorization."""
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == int(tenant_id),
            PlatformConfig.config_type == "FEATURES",
            PlatformConfig.config_key == "-",
            PlatformConfig.is_deleted.is_(False),
        )).first()
        return {
            "payload": dict(row.config_json or {}) if row else {},
            "version": int(row.version or 1) if row else 0,
        }
    finally:
        db.close()


def features_projection(tenant_id: int) -> dict:
    from app.services import platform_service

    tenant = platform_service.get_tenant(int(tenant_id))
    meta = platform_service.tenant_meta(int(tenant_id))
    package = platform_service.get_package(str(meta.get("packageCode") or "professional"))
    canonical = effective_features(int(tenant_id))
    legacy = legacy_override_snapshot(int(tenant_id))
    drift = {
        key: {"commercial": bool(canonical.get(key, False)), "legacy": bool(value)}
        for key, value in legacy["payload"].items()
        if key in D.FEATURE_KEYS and bool(value) != bool(canonical.get(key, False))
    }
    return {
        "tenantId": str(tenant_id),
        "tenantName": tenant.get("tenantName"),
        "packageCode": package.get("packageCode"),
        "features": canonical,
        "packageFeatures": dict(canonical),
        "authoritySource": authority_source(int(tenant_id)),
        "commercialOrderNo": meta.get("lastCommercialOrderNo") or None,
        "legacyOverride": legacy["payload"],
        "legacyOverrideVersion": legacy["version"],
        "legacyOverrideReadOnly": bool(legacy["payload"]),
        "legacyDrift": drift,
        "repairRequired": bool(drift),
    }


def install_platform_service_adapter() -> None:
    """Make legacy callers consume the new runtime authority without editing the frozen bundle."""
    global _ORIGINAL_PRELOADED
    from app.services import platform_service

    platform_service.effective_features = effective_features
    platform_service.feature_enabled = feature_enabled

    if _ORIGINAL_PRELOADED is None:
        _ORIGINAL_PRELOADED = platform_service._tenant_row_preloaded

    original = _ORIGINAL_PRELOADED

    def _tenant_row_preloaded_without_legacy_feature_override(
        t, meta: dict, *, students: int, users: int, school_admins: int, teachers: int,
        package_overrides: dict[str, dict], feature_override: dict | None,
    ) -> dict:
        # The frozen list reader may still preload grandfathered FEATURES rows.
        # Drop them before building allowX projections so list/detail and backend
        # authorization use the same paid-order/package truth.
        return original(
            t, meta,
            students=students,
            users=users,
            school_admins=school_admins,
            teachers=teachers,
            package_overrides=package_overrides,
            feature_override=None,
        )

    platform_service._tenant_row_preloaded = _tenant_row_preloaded_without_legacy_feature_override
