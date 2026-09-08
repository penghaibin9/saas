"""Install M2 commercial readers/writers on the canonical service facades.

The repository already installs platform runtime guards from ``app.services`` so
HTTP, CLI and worker imports receive the same service objects. M2 follows that
pattern instead of forking a second entitlement facade or editing the frozen
platform bundle.
"""
from __future__ import annotations

from typing import Any


def install(platform_service_module: Any) -> Any:
    from app.services import commercial_entitlement_authority_service as authority
    from app.services import commercial_order_item_service as itemized
    from app.services import module_subscription_service as subscriptions

    if getattr(authority, "_module_commerce_m2_installed", False):
        return platform_service_module

    legacy_state = authority.commercial_state
    original_order_action = platform_service_module.order_action
    original_activation_state = platform_service_module.paid_order_activation_state

    def legacy_commercial_state_for_reconciliation(tenant_id: int) -> dict:
        state = legacy_state(int(tenant_id))
        return {**state, "readerVersion": "LEGACY"}

    def commercial_state(tenant_id: int) -> dict:
        tid = int(tenant_id)
        try:
            mode = subscriptions.reader_version(tid)
        except Exception as exc:
            authority._LOG.exception("commercial reader profile unavailable tenant=%s", tid)
            return {
                "verified": False, "authoritySource": "COMMERCIAL_READER_UNAVAILABLE",
                "packageCode": None, "packageVersion": 0, "features": authority._zero_features(),
                "commercialOrderNo": None, "repairRequired": True,
                "readerVersion": "UNKNOWN", "error": type(exc).__name__,
            }
        if mode != "MODULE_V2":
            state = legacy_state(tid)
            state.setdefault("readerVersion", "LEGACY")
            return state
        try:
            from app.services.tenant_effective_state_service import effective_state_from_records

            tenant = authority._tenant_snapshot(tid)
            meta = platform_service_module.tenant_meta(tid)
            lifecycle = effective_state_from_records(
                row_status=tenant["tenantStatus"], meta=meta, strict=True,
            )
            if not lifecycle.get("writable"):
                return {
                    "verified": False, "authoritySource": "MODULE_V2_TENANT_INACTIVE",
                    "packageCode": "module-v2", "packageVersion": 1,
                    "features": authority._zero_features(), "moduleEntitlements": [], "quotas": {},
                    "commercialOrderNo": None, "repairRequired": False,
                    "readerVersion": "MODULE_V2", "migrationStatus": None, "profileVersion": None,
                }
            projected = subscriptions.module_projection(tid)
            if projected.get("readerVersion") != "MODULE_V2" or projected.get("verified") is not True:
                raise RuntimeError("module reader returned an unverified projection")
            return {
                "verified": True, "authoritySource": "MODULE_V2",
                "packageCode": "module-v2", "packageVersion": 1,
                "features": dict(projected["features"]),
                "moduleEntitlements": list(projected.get("moduleEntitlements") or []),
                "quotas": dict(projected.get("quotas") or {}),
                "commercialOrderNo": None, "repairRequired": False,
                "readerVersion": "MODULE_V2", "sourceCount": int(projected.get("sourceCount") or 0),
                "migrationStatus": projected.get("migrationStatus"),
                "profileVersion": projected.get("profileVersion"),
            }
        except Exception as exc:
            authority._LOG.exception("module-v2 commercial projection failed tenant=%s", tid)
            return {
                "verified": False, "authoritySource": "MODULE_V2_UNAVAILABLE",
                "packageCode": "module-v2", "packageVersion": 1,
                "features": authority._zero_features(), "moduleEntitlements": [], "quotas": {},
                "commercialOrderNo": None, "repairRequired": True,
                "readerVersion": "MODULE_V2", "error": type(exc).__name__,
            }

    def paid_order_activation_state(order, tenant, meta: dict):
        if str(getattr(order, "package_code", "") or "").upper() == "MODULE_V2":
            try:
                rows = itemized.order_items(int(order.id))
                if rows and all(str(row.fulfillment_status or "") == "FULFILLED" for row in rows):
                    return "ACTIVE", False
                return "REPAIR_REQUIRED", True
            except Exception:
                return "REPAIR_REQUIRED", True
        return original_activation_state(order, tenant, meta)

    def order_action(order_no: str, action: str, *, expected_version: int, reason: str):
        native_itemized = False
        try:
            from sqlalchemy import select
            from app.models import PlatformOrder
            with platform_service_module.session() as db:
                order = db.scalars(select(PlatformOrder).where(
                    PlatformOrder.order_no == str(order_no),
                    PlatformOrder.is_deleted.is_(False),
                )).first()
                if order is not None:
                    native_itemized = itemized.is_native_itemized_order(int(order.id), db_session=db)
        except Exception:
            native_itemized = False

        if native_itemized and action == "repair-activation":
            return subscriptions.activate_paid_order_items(
                order_no, expected_version=int(expected_version), reason=reason,
            )

        result = original_order_action(
            order_no, action, expected_version=int(expected_version), reason=reason,
        )
        if not (native_itemized and action == "mark-paid"):
            return result
        try:
            return subscriptions.activate_paid_order_items(
                order_no, expected_version=int(result["version"]), reason=reason,
            )
        except Exception:
            return {
                **result, "status": "paid", "tenantActivated": False,
                "repairTaskRequired": True, "rightsMaterialized": False,
            }

    authority.legacy_commercial_state_for_reconciliation = legacy_commercial_state_for_reconciliation
    authority.commercial_state = commercial_state
    authority._module_commerce_m2_installed = True
    platform_service_module.paid_order_activation_state = paid_order_activation_state
    platform_service_module.order_action = order_action
    return platform_service_module
