"""Commercial entitlement authority for W1 runtime cutover.

Normal paid entitlement is accepted only when a real paid ``PlatformOrder`` is
materialized onto the same tenant/package. Trial is a separate commercial state;
controlled exceptions must carry the explicit approval evidence already enforced
by ``tenant_effective_state_service``. Legacy tenant ``PlatformConfig(FEATURES)``
rows are reconciliation evidence only and never participate in runtime access.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select

from app.services import platform_defaults as D

_LOG = logging.getLogger("platform.commercial-entitlement")
_ORIGINAL_PRELOADED = None
_ORIGINAL_TRANSITION = None


def _zero_features() -> dict[str, bool]:
    return {key: False for key in D.FEATURE_KEYS}


def _package_features(package: dict) -> dict[str, bool]:
    merged = {**D.DEFAULT_FEATURES, **(package.get("features") or {})}
    return {key: bool(merged.get(key, False)) for key in D.FEATURE_KEYS}


def _active_paid_order(tenant_id: int, meta: dict, package_code: str):
    """Return the paid order that actually authorizes the materialized package.

    New orders must be the exact ``lastCommercialOrderNo`` written by activation.
    Pre-marker historical paid rows are accepted only when their paid service
    period is still active and the materialized tenant package matches.
    """
    from app.db.session import get_sessionmaker
    from app.models import PlatformOrder, Tenant
    from app.services import platform_service

    db = get_sessionmaker()()
    try:
        tenant = db.scalars(select(Tenant).where(
            Tenant.id == int(tenant_id), Tenant.is_deleted.is_(False),
        )).first()
        marker = str(meta.get("lastCommercialOrderNo") or "").strip()
        if marker:
            order = db.scalars(select(PlatformOrder).where(
                PlatformOrder.tenant_id == int(tenant_id),
                PlatformOrder.order_no == marker,
                PlatformOrder.status == "paid",
                PlatformOrder.is_deleted.is_(False),
            )).first()
            if order is None or str(order.package_code or "") != package_code:
                return None, "PAID_ORDER_EVIDENCE_MISMATCH"
            activation_state, repair_required = platform_service.paid_order_activation_state(order, tenant, meta)
            if activation_state != "ACTIVE" or repair_required:
                return None, "PAID_ORDER_ACTIVATION_REPAIR_REQUIRED"
            return order, "PAID_ORDER"

        # N-1 compatibility: historical paid rows predate lastCommercialOrderNo.
        # They are commercial facts, unlike FEATURES/TENANT_META package edits.
        rows = db.scalars(select(PlatformOrder).where(
            PlatformOrder.tenant_id == int(tenant_id),
            PlatformOrder.package_code == package_code,
            PlatformOrder.status == "paid",
            PlatformOrder.is_deleted.is_(False),
        ).order_by(PlatformOrder.id.desc())).all()
        now = datetime.now()
        for order in rows:
            # version>=2 belongs to the new activation protocol and therefore
            # must have an exact marker; never silently downgrade it to legacy.
            if int(order.version or 0) >= 2:
                continue
            if order.start_at and order.start_at.replace(tzinfo=None) > now:
                continue
            if order.end_at and order.end_at.replace(tzinfo=None) <= now:
                continue
            if tenant is None or str(tenant.status or "").upper() != "ACTIVE":
                continue
            if str(meta.get("status") or "").lower() != "active":
                continue
            if str(meta.get("packageCode") or "") != package_code:
                continue
            return order, "LEGACY_PAID_ORDER"
        return None, "COMMERCIAL_ORDER_REQUIRED"
    finally:
        db.close()


def commercial_state(tenant_id: int) -> dict:
    """Resolve one commercial truth record used by every runtime feature check."""
    from app.services import platform_service

    tid = int(tenant_id)
    platform_service.get_tenant(tid)
    meta = platform_service.tenant_meta(tid)
    package_code = str(meta.get("packageCode") or "trial").strip()
    package = platform_service.get_package(package_code)
    if str(package.get("packageCode") or "") != package_code:
        return {
            "verified": False,
            "authoritySource": "PACKAGE_NOT_FOUND",
            "packageCode": package_code,
            "packageVersion": 0,
            "features": _zero_features(),
            "commercialOrderNo": None,
            "repairRequired": True,
        }

    status = str(meta.get("status") or "").strip().lower()
    authority = str(meta.get("lastCommercialAuthority") or "").strip().upper()
    approval_ref = str(meta.get("lastCommercialApprovalRef") or "").strip()

    # Trial is a legitimate non-paid commercial state. It never authorizes a
    # formal package merely because somebody edited TENANT_META.packageCode.
    if package_code == "trial" and status in {"trial", "active"}:
        return {
            "verified": True,
            "authoritySource": "TRIAL",
            "packageCode": package_code,
            "packageVersion": int(package.get("version") or 0),
            "features": _package_features(package),
            "commercialOrderNo": None,
            "repairRequired": False,
        }

    if authority == "CONTROLLED_EXCEPTION":
        if len(approval_ref) < 5:
            return {
                "verified": False,
                "authoritySource": "CONTROLLED_EXCEPTION_EVIDENCE_MISSING",
                "packageCode": package_code,
                "packageVersion": int(package.get("version") or 0),
                "features": _zero_features(),
                "commercialOrderNo": None,
                "repairRequired": True,
            }
        return {
            "verified": True,
            "authoritySource": "CONTROLLED_EXCEPTION",
            "packageCode": package_code,
            "packageVersion": int(package.get("version") or 0),
            "features": _package_features(package),
            "commercialOrderNo": None,
            "approvalRef": approval_ref,
            "repairRequired": False,
        }

    order, source = _active_paid_order(tid, meta, package_code)
    if order is None:
        return {
            "verified": False,
            "authoritySource": source,
            "packageCode": package_code,
            "packageVersion": int(package.get("version") or 0),
            "features": _zero_features(),
            "commercialOrderNo": str(meta.get("lastCommercialOrderNo") or "") or None,
            "repairRequired": True,
        }
    return {
        "verified": True,
        "authoritySource": source,
        "packageCode": package_code,
        "packageVersion": int(package.get("version") or 0),
        "features": _package_features(package),
        "commercialOrderNo": str(order.order_no),
        "orderVersion": int(order.version or 0),
        "serviceStartAt": order.start_at.isoformat(timespec="seconds") if order.start_at else None,
        "serviceEndAt": order.end_at.isoformat(timespec="seconds") if order.end_at else None,
        "repairRequired": source != "PAID_ORDER",
    }


def effective_features(tenant_id: int) -> dict[str, bool]:
    """Return verified commercial entitlement; unverified formal state fails closed."""
    return dict(commercial_state(int(tenant_id))["features"])


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
    return str(commercial_state(int(tenant_id))["authoritySource"])


def legacy_override_snapshot(tenant_id: int) -> dict:
    """Read grandfathered FEATURES only for reconciliation; never for authorization."""
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

    tid = int(tenant_id)
    tenant = platform_service.get_tenant(tid)
    state = commercial_state(tid)
    canonical = dict(state["features"])
    legacy = legacy_override_snapshot(tid)
    drift = {
        key: {"commercial": bool(canonical.get(key, False)), "legacy": bool(value)}
        for key, value in legacy["payload"].items()
        if key in D.FEATURE_KEYS and bool(value) != bool(canonical.get(key, False))
    }
    return {
        "tenantId": str(tid),
        "tenantName": tenant.get("tenantName"),
        "packageCode": state["packageCode"],
        "packageVersion": state.get("packageVersion", 0),
        "features": canonical,
        "packageFeatures": dict(canonical),
        "commercialVerified": bool(state["verified"]),
        "authoritySource": state["authoritySource"],
        "commercialOrderNo": state.get("commercialOrderNo"),
        "serviceStartAt": state.get("serviceStartAt"),
        "serviceEndAt": state.get("serviceEndAt"),
        "legacyOverride": legacy["payload"],
        "legacyOverrideVersion": legacy["version"],
        "legacyOverrideReadOnly": bool(legacy["payload"]),
        "legacyDrift": drift,
        "repairRequired": bool(state.get("repairRequired")) or bool(drift),
    }


def _validate_paid_transition(tenant_id: int, payload: dict) -> None:
    """Do not trust a caller-supplied PAID_ORDER authority string by itself."""
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import PlatformOrder

    order_no = str(payload.get("orderNo") or "").strip()
    package_code = str(payload.get("packageCode") or "").strip()
    if not order_no or not package_code:
        raise AppException("COMMERCIAL_ORDER_REQUIRED", "已支付订单激活必须提供 orderNo 与 packageCode", http_status=409)
    db = get_sessionmaker()()
    try:
        order = db.scalars(select(PlatformOrder).where(
            PlatformOrder.tenant_id == int(tenant_id),
            PlatformOrder.order_no == order_no,
            PlatformOrder.package_code == package_code,
            PlatformOrder.status == "paid",
            PlatformOrder.is_deleted.is_(False),
        )).first()
        if order is None:
            raise AppException("COMMERCIAL_ORDER_REQUIRED", "未找到与租户和套餐匹配的已支付订单", http_status=409)
        requested_expire = str(payload.get("expireAt") or "").strip()
        actual_expire = order.end_at.isoformat(timespec="seconds") if order.end_at else ""
        if requested_expire and actual_expire and requested_expire != actual_expire:
            raise AppException("COMMERCIAL_ORDER_MISMATCH", "订单服务截止时间与激活请求不一致", http_status=409)
    finally:
        db.close()


def install_platform_service_adapter() -> None:
    """Make legacy callers consume verified commercial truth without editing frozen bundles."""
    global _ORIGINAL_PRELOADED, _ORIGINAL_TRANSITION
    from app.services import platform_service
    from app.services import tenant_effective_state_service as lifecycle

    platform_service.effective_features = effective_features
    platform_service.feature_enabled = feature_enabled

    if _ORIGINAL_PRELOADED is None:
        _ORIGINAL_PRELOADED = platform_service._tenant_row_preloaded
    original_preloaded = _ORIGINAL_PRELOADED

    def _tenant_row_preloaded_without_legacy_features(
        t, meta: dict, *, students: int, users: int, school_admins: int, teachers: int,
        package_overrides: dict[str, dict], feature_override: dict | None,
    ) -> dict:
        # Keep PLAT-02 constant-query: this function runs once per listed tenant,
        # so it must never open a session. Exact paid-order verification belongs
        # to detail/runtime gates; list projection exposes UNKNOWN when only an
        # order marker is present.
        row = original_preloaded(
            t, meta,
            students=students,
            users=users,
            school_admins=school_admins,
            teachers=teachers,
            package_overrides=package_overrides,
            feature_override=None,
        )
        package_code = str(meta.get("packageCode") or "trial")
        status = str(meta.get("status") or "").lower()
        authority = str(meta.get("lastCommercialAuthority") or "").upper()
        approval_ref = str(meta.get("lastCommercialApprovalRef") or "")
        order_no = str(meta.get("lastCommercialOrderNo") or "")
        if package_code == "trial" and status in {"trial", "active"}:
            source, verified, repair = "TRIAL", True, False
        elif authority == "CONTROLLED_EXCEPTION" and len(approval_ref) >= 5:
            source, verified, repair = "CONTROLLED_EXCEPTION", True, False
        elif order_no:
            source, verified, repair = "PAID_ORDER_EVIDENCE_PRESENT", None, None
        else:
            source, verified, repair = "COMMERCIAL_ORDER_REQUIRED", False, True
            for key in (
                "allowImport", "allowExport", "allowFileUpload", "allowMiniapp",
                "allowGraduation", "allowInternship", "allowEmployment", "allowRiskWarning",
                "allowCustomBrand", "allowWorkflowConfig", "allowApiAccess",
            ):
                row[key] = False
        row["commercialAuthoritySource"] = source
        row["commercialAuthorityVerified"] = verified
        row["commercialRepairRequired"] = repair
        return row

    platform_service._tenant_row_preloaded = _tenant_row_preloaded_without_legacy_features

    if _ORIGINAL_TRANSITION is None:
        _ORIGINAL_TRANSITION = lifecycle.apply_transition
    original_transition = _ORIGINAL_TRANSITION

    def _governed_transition(tenant_id: int, action: str, **kwargs):
        from app.core.exceptions import AppException

        normalized = str(action or "").strip().lower()
        if normalized in {"change-package", "quota"}:
            raise AppException(
                "COMMERCIAL_ORDER_REQUIRED",
                "商业套餐与商业额度不能直接修改；请通过已支付订单生效，受控特批请走 convert-to-paid",
                http_status=409,
            )
        if normalized == "convert-to-paid" and str(kwargs.get("commercial_authority") or "").strip().upper() == "PAID_ORDER":
            _validate_paid_transition(int(tenant_id), dict(kwargs.get("payload") or {}))
        return original_transition(tenant_id, action, **kwargs)

    lifecycle.apply_transition = _governed_transition
