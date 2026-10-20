"""M2 module entitlement source aggregation and reader cutover.

``commercial_entitlement_authority_service`` remains the only runtime read facade.
This module owns MODULE_V2 source facts and never ORs them with legacy FEATURES.
A tenant profile chooses exactly one reader version. Existing formal customers stay
LEGACY until shadow reconciliation is explicitly accepted; fresh trial tenants can
cut to MODULE_V2 when their first real itemized paid order is fulfilled.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker
from app.services import platform_defaults as D

CANONICAL_MODULES = ("internship", "graduationDesign", "studentAffairs", "academicAffairs")


def _zero_features() -> dict[str, bool]:
    return {key: False for key in D.FEATURE_KEYS}


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_db() -> None:
    if not db_enabled():
        raise AppException("SERVER_ERROR", "模块商业授权需要数据库")


def _profile(db, tenant_id: int, *, lock: bool = False):
    from app.models import TenantCommercialProfile
    q = select(TenantCommercialProfile).where(
        TenantCommercialProfile.tenant_id == int(tenant_id),
        TenantCommercialProfile.is_deleted.is_(False),
    )
    if lock:
        q = q.with_for_update()
    return db.scalars(q).first()


def reader_version(tenant_id: int) -> str:
    _require_db()
    db = get_sessionmaker()()
    try:
        row = _profile(db, tenant_id)
        return str(row.reader_version if row else "LEGACY")
    finally:
        db.close()


def _materialize_v2_tenant_lifecycle(db, tenant_id: int, *, expire_at: datetime, order_no: str) -> None:
    """Keep the hard tenant lifecycle active while module sources own individual windows.

    ``packageCode=module-v2`` is intentionally not a legacy package. If the V2 reader
    profile disappeared, legacy authority must not reinterpret this marker as a paid
    package and widen access. The global expireAt is only the latest active contract
    horizon; per-module access still comes exclusively from source windows.
    """
    from app.models import PlatformConfig
    row = db.scalars(select(PlatformConfig).where(
        PlatformConfig.tenant_id == int(tenant_id),
        PlatformConfig.config_type == "TENANT_META",
        PlatformConfig.config_key == "-",
        PlatformConfig.is_deleted.is_(False),
    ).with_for_update()).first()
    payload = dict(row.config_json or {}) if row else {}
    previous = payload.get("expireAt")
    latest = expire_at.replace(tzinfo=None)
    if previous:
        try:
            latest = max(latest, datetime.fromisoformat(str(previous).replace("Z", "+00:00")).replace(tzinfo=None))
        except (TypeError, ValueError):
            pass
    payload.update({
        "status": "active",
        "packageCode": "module-v2",
        "expireAt": latest.isoformat(timespec="seconds"),
        "lastCommercialAuthority": "MODULE_V2",
        "lastCommercialOrderNo": str(order_no),
    })
    if row is None:
        row = PlatformConfig(tenant_id=int(tenant_id), config_type="TENANT_META", config_key="-",
                             config_json=payload, enabled=True, status="ACTIVE", version=1)
        db.add(row)
    else:
        row.config_json = payload
        row.enabled = True
        row.status = "ACTIVE"
        row.version = int(row.version or 0) + 1


def _auto_cutover_allowed(tenant_id: int) -> bool:
    """Only a fresh trial/unverified tenant may auto-cut on its first modular sale."""
    from app.services import platform_service
    meta = platform_service.tenant_meta(int(tenant_id))
    package = str(meta.get("packageCode") or "trial").strip()
    authority = str(meta.get("lastCommercialAuthority") or "").strip().upper()
    marker = str(meta.get("lastCommercialOrderNo") or "").strip()
    return package == "trial" and not marker and authority not in {"PAID_ORDER", "CONTROLLED_EXCEPTION"}


def _quota_projection(rows: list) -> dict:
    values: dict[str, dict] = {}
    replace_candidates: dict[str, tuple[datetime, int, int, str]] = {}
    for row in rows:
        for key, rule in (row.quota_snapshot_json or {}).items():
            try:
                limit = int(rule.get("limit"))
            except Exception:
                continue
            aggregation = str(rule.get("aggregation") or "")
            unit = str(rule.get("unit") or "")
            if aggregation == "MAX":
                current = values.get(key)
                if current is None or limit > int(current["limit"]):
                    values[key] = {"limit": limit, "unit": unit, "aggregation": "MAX"}
            elif aggregation == "SUM":
                current = values.setdefault(key, {"limit": 0, "unit": unit, "aggregation": "SUM"})
                if current["unit"] != unit:
                    raise AppException("DATA_CONFLICT", f"模块额度 {key} 的单位冲突", http_status=409)
                current["limit"] = int(current["limit"]) + limit
            elif aggregation == "REPLACE":
                candidate = (row.starts_at, int(row.id or 0), limit, unit)
                if key not in replace_candidates or candidate[:2] > replace_candidates[key][:2]:
                    replace_candidates[key] = candidate
    for key, (_when, _rid, limit, unit) in replace_candidates.items():
        values[key] = {"limit": limit, "unit": unit, "aggregation": "REPLACE"}
    return values


def module_projection(tenant_id: int, *, now: datetime | None = None, db_session=None) -> dict:
    _require_db()
    from app.models import TenantModuleState, TenantModuleSubscriptionSource

    current = (now or datetime.utcnow()).replace(tzinfo=None)

    def read(db):
        profile = _profile(db, tenant_id)
        if profile is None or str(profile.reader_version) != "MODULE_V2":
            return {
                "readerVersion": "LEGACY",
                "verified": False,
                "features": _zero_features(),
                "moduleEntitlements": [],
                "quotas": {},
                "sourceCount": 0,
            }
        states = {
            row.module_key: row
            for row in db.scalars(select(TenantModuleState).where(
                TenantModuleState.tenant_id == int(tenant_id),
                TenantModuleState.is_deleted.is_(False),
            )).all()
        }
        sources = list(db.scalars(select(TenantModuleSubscriptionSource).where(
            TenantModuleSubscriptionSource.tenant_id == int(tenant_id),
            TenantModuleSubscriptionSource.status.in_(("ACTIVE", "SCHEDULED")),
            TenantModuleSubscriptionSource.starts_at <= current,
            TenantModuleSubscriptionSource.ends_at > current,
            TenantModuleSubscriptionSource.is_deleted.is_(False),
        ).order_by(TenantModuleSubscriptionSource.starts_at, TenantModuleSubscriptionSource.id)).all())
        active = []
        for row in sources:
            state = states.get(row.module_key)
            if state is None or int(state.generation) != int(row.module_generation):
                continue
            if str(state.data_state or "").upper() == "PURGED":
                continue
            active.append(row)
        features = _zero_features()
        modules = set()
        for row in active:
            if row.module_key not in CANONICAL_MODULES:
                raise AppException("DATA_CONFLICT", "存在未知模块授权来源，已停止授权计算", http_status=409)
            modules.add(row.module_key)
            for key, value in (row.feature_snapshot_json or {}).items():
                if key not in features or type(value) is not bool:
                    raise AppException("DATA_CONFLICT", "授权来源功能快照已漂移，已停止授权计算", http_status=409)
                features[key] = features[key] or value
        return {
            "readerVersion": "MODULE_V2",
            "verified": True,
            "features": features,
            "moduleEntitlements": sorted(modules),
            "quotas": _quota_projection(active),
            "sourceCount": len(active),
            "profileVersion": int(profile.version or 0),
            "migrationStatus": str(profile.migration_status or ""),
        }

    if db_session is not None:
        return read(db_session)
    db = get_sessionmaker()()
    try:
        return read(db)
    finally:
        db.close()


def activate_paid_order_items(order_no: str, *, expected_version: int, reason: str) -> dict:
    _require_db()
    from app.models import (
        CommercialOrderItem, PlatformOrder, Tenant, TenantCommercialProfile,
        TenantModuleState, TenantModuleSubscriptionSource,
    )
    from app.services import audit_log

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "授权激活原因至少5个字符", http_status=422)
    db = get_sessionmaker()()
    try:
        order = db.scalars(select(PlatformOrder).where(
            PlatformOrder.order_no == str(order_no),
            PlatformOrder.is_deleted.is_(False),
        ).with_for_update()).first()
        if order is None:
            raise AppException("DATA_NOT_FOUND", "订单不存在", http_status=404)
        current_version = max(1, int(order.version or 0))
        if int(expected_version) != current_version:
            raise AppException("DATA_CONFLICT", "订单已更新，请刷新后重试", http_status=409)
        if str(order.status or "").lower() != "paid":
            raise AppException("DATA_CONFLICT", "只有已支付分项订单可以激活", http_status=409)
        tenant = db.scalars(select(Tenant).where(
            Tenant.id == int(order.tenant_id), Tenant.is_deleted.is_(False),
        ).with_for_update()).first()
        if tenant is None:
            raise AppException("DATA_NOT_FOUND", "租户不存在", http_status=404)
        items = list(db.scalars(select(CommercialOrderItem).where(
            CommercialOrderItem.order_id == int(order.id),
            CommercialOrderItem.is_deleted.is_(False),
        ).order_by(CommercialOrderItem.line_no).with_for_update()).all())
        if not items or any(row.fulfillment_status == "LEGACY_UNALLOCATED" for row in items):
            raise AppException("DATA_CONFLICT", "该订单不是可自动履约的模块分项合同", http_status=409)
        now = datetime.utcnow()
        for item in items:
            if item.module_key not in CANONICAL_MODULES or not item.sku_snapshot_json:
                raise AppException("DATA_CONFLICT", "订单项缺少规范模块快照", http_status=409)
            from app.services.commercial_catalog_contract import Snapshot, canonical
            snap = Snapshot(canonical(item.sku_snapshot_json))
            if snap.content_hash != str(item.sku_content_hash or ""):
                raise AppException("DATA_CONFLICT", "订单项商品快照指纹不一致", http_status=409)
            state = db.scalars(select(TenantModuleState).where(
                TenantModuleState.tenant_id == int(order.tenant_id),
                TenantModuleState.module_key == item.module_key,
                TenantModuleState.is_deleted.is_(False),
            ).with_for_update()).first()
            requested_generation = int(item.module_generation or 0)
            if state is None:
                if requested_generation != 1:
                    raise AppException("DATA_CONFLICT", "首次开通模块代次必须为1", http_status=409)
                state = TenantModuleState(
                    tenant_id=int(order.tenant_id), module_key=item.module_key,
                    generation=1, lifecycle_version=1, data_state="AVAILABLE",
                )
                db.add(state)
                db.flush()
            elif int(state.generation) != requested_generation:
                raise AppException("DATA_CONFLICT", "模块代次已变化，旧订单不能复活历史数据", http_status=409)
            source_ref = f"order-item:{item.id}"
            source = db.scalars(select(TenantModuleSubscriptionSource).where(
                TenantModuleSubscriptionSource.tenant_id == int(order.tenant_id),
                TenantModuleSubscriptionSource.source_type == "PAID_ORDER_ITEM",
                TenantModuleSubscriptionSource.source_ref == source_ref,
                TenantModuleSubscriptionSource.module_key == item.module_key,
                TenantModuleSubscriptionSource.is_deleted.is_(False),
            ).with_for_update()).first()
            if source is None:
                source = TenantModuleSubscriptionSource(
                    tenant_id=int(order.tenant_id), module_key=item.module_key,
                    module_generation=requested_generation,
                    source_type="PAID_ORDER_ITEM", source_ref=source_ref,
                    order_item_id=int(item.id),
                    feature_snapshot_json=dict(item.feature_snapshot_json or {}),
                    quota_snapshot_json=dict(item.quota_snapshot_json or {}),
                    starts_at=item.service_start_at, ends_at=item.service_end_at,
                    status="SCHEDULED" if item.service_start_at and item.service_start_at > now else "ACTIVE",
                    activated_at=now,
                )
                db.add(source)
            item.fulfillment_status = "FULFILLED"
            item.fulfilled_at = now
            item.version = int(item.version or 0) + 1

        profile = _profile(db, int(order.tenant_id), lock=True)
        auto_cutover = False
        if profile is None:
            auto_cutover = _auto_cutover_allowed(int(order.tenant_id))
            profile = TenantCommercialProfile(
                tenant_id=int(order.tenant_id),
                reader_version="MODULE_V2" if auto_cutover else "LEGACY",
                migration_status="NEW_MODULE_CUSTOMER" if auto_cutover else "SHADOW_READY",
                switched_at=now if auto_cutover else None,
                switch_reason=reason_text if auto_cutover else "Existing commercial state requires shadow reconciliation",
            )
            db.add(profile)
        if str(profile.reader_version) == "MODULE_V2":
            max_end = max(item.service_end_at for item in items if item.service_end_at is not None)
            _materialize_v2_tenant_lifecycle(
                db, int(order.tenant_id), expire_at=max_end, order_no=str(order.order_no),
            )
        order.version = current_version + 1
        audit_log.record_critical_in_session(
            db, "COMMERCIAL_MODULE_SOURCE_ACTIVATE", f"order:{order.order_no}",
            detail={"tenantId": str(order.tenant_id), "itemCount": len(items),
                    "readerVersion": profile.reader_version, "autoCutover": auto_cutover,
                    "reason": reason_text},
            tenant_id=int(order.tenant_id), resource_id=str(order.id),
        )
        db.commit()
        if str(profile.reader_version) == "MODULE_V2":
            from app.services.auth_service_db import invalidate_tenant_subject_caches
            invalidate_tenant_subject_caches(int(order.tenant_id))
        return {
            "orderNo": order.order_no,
            "status": "paid",
            "version": int(order.version),
            "tenantActivated": str(profile.reader_version) == "MODULE_V2",
            "readerVersion": str(profile.reader_version),
            "repairTaskRequired": str(profile.reader_version) != "MODULE_V2",
            "cutoverReviewRequired": str(profile.reader_version) != "MODULE_V2",
            "rightsMaterialized": True,
            "itemCount": len(items),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cancel_subscription_source_now(tenant_id: int, source_id: int, *, expected_version: int, reason: str) -> dict:
    """Cancel one commercial source without touching sibling sources or tenant data."""
    _require_db()
    from app.models import TenantModuleSubscriptionSource
    from app.services import audit_log

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "退订来源原因至少5个字符", http_status=422)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(TenantModuleSubscriptionSource).where(
            TenantModuleSubscriptionSource.id == int(source_id),
            TenantModuleSubscriptionSource.tenant_id == int(tenant_id),
            TenantModuleSubscriptionSource.is_deleted.is_(False),
        ).with_for_update()).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "模块订阅来源不存在", http_status=404)
        current_version = int(row.version or 0)
        if int(expected_version) != current_version:
            raise AppException("DATA_CONFLICT", "订阅来源已变化，请刷新后重试", http_status=409)
        if row.status == "CANCELLED":
            return {"sourceId": str(row.id), "status": "CANCELLED", "version": current_version, "replayed": True}
        row.status = "CANCELLED"
        row.cancelled_at = datetime.utcnow()
        row.version = current_version + 1
        audit_log.record_critical_in_session(
            db, "COMMERCIAL_MODULE_SOURCE_CANCEL", f"module-source:{row.id}",
            detail={"tenantId": str(tenant_id), "moduleKey": row.module_key, "reason": reason_text},
            tenant_id=int(tenant_id), resource_id=str(row.id),
        )
        db.commit()
        from app.services.auth_service_db import invalidate_tenant_subject_caches
        invalidate_tenant_subject_caches(int(tenant_id))
        return {"sourceId": str(row.id), "status": "CANCELLED", "version": int(row.version), "replayed": False}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def shadow_reconcile_tenant(tenant_id: int, *, legacy_features: dict[str, bool]) -> dict:
    projected = module_projection(int(tenant_id))
    v2 = projected["features"] if projected.get("readerVersion") == "MODULE_V2" else _shadow_source_projection(int(tenant_id))["features"]
    legacy = {key: bool(legacy_features.get(key, False)) for key in D.FEATURE_KEYS}
    legacy_on = sorted(key for key, value in legacy.items() if value)
    v2_on = sorted(key for key, value in v2.items() if value)
    return {
        "tenantId": str(tenant_id),
        "legacyEnabled": legacy_on,
        "moduleV2Enabled": v2_on,
        "matches": legacy_on == v2_on,
        "legacyDigest": _sha(legacy),
        "moduleV2Digest": _sha(v2),
    }


def _shadow_source_projection(tenant_id: int) -> dict:
    """Read source facts without switching the runtime reader; never used for access."""
    from app.models import TenantModuleState, TenantModuleSubscriptionSource
    db = get_sessionmaker()()
    try:
        current = datetime.utcnow()
        states = {r.module_key: r for r in db.scalars(select(TenantModuleState).where(
            TenantModuleState.tenant_id == int(tenant_id), TenantModuleState.is_deleted.is_(False))).all()}
        rows = list(db.scalars(select(TenantModuleSubscriptionSource).where(
            TenantModuleSubscriptionSource.tenant_id == int(tenant_id),
            TenantModuleSubscriptionSource.status.in_(("ACTIVE", "SCHEDULED")),
            TenantModuleSubscriptionSource.starts_at <= current,
            TenantModuleSubscriptionSource.ends_at > current,
            TenantModuleSubscriptionSource.is_deleted.is_(False),
        )).all())
        features = _zero_features()
        kept = []
        for row in rows:
            state = states.get(row.module_key)
            if state is None or int(state.generation) != int(row.module_generation) or str(state.data_state).upper() == "PURGED":
                continue
            kept.append(row)
            for key, value in (row.feature_snapshot_json or {}).items():
                if key not in features or type(value) is not bool:
                    raise AppException("DATA_CONFLICT", "影子授权来源功能快照无效", http_status=409)
                features[key] = features[key] or value
        return {"features": features, "sourceCount": len(kept)}
    finally:
        db.close()


def switch_reader_to_module_v2(tenant_id: int, *, expected_version: int, reason: str,
                               legacy_features: dict[str, bool]) -> dict:
    _require_db()
    from app.models import Tenant, TenantCommercialProfile
    from app.services import audit_log

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "切换原因至少5个字符", http_status=422)
    comparison = shadow_reconcile_tenant(int(tenant_id), legacy_features=legacy_features)
    if not comparison["matches"]:
        raise AppException("DATA_CONFLICT", "新旧商业授权仍有未解释差异，禁止切换", http_status=409, details=comparison)
    db = get_sessionmaker()()
    try:
        tenant = db.scalars(select(Tenant).where(Tenant.id == int(tenant_id), Tenant.is_deleted.is_(False)).with_for_update()).first()
        if tenant is None:
            raise AppException("DATA_NOT_FOUND", "租户不存在", http_status=404)
        profile = _profile(db, tenant_id, lock=True)
        if profile is None:
            profile = TenantCommercialProfile(tenant_id=int(tenant_id), reader_version="LEGACY", migration_status="SHADOW_READY")
            db.add(profile); db.flush()
        current_version = int(profile.version or 0)
        if int(expected_version) != current_version:
            raise AppException("DATA_CONFLICT", "商业读取版本已变化，请重新对账", http_status=409)
        profile.reader_version = "MODULE_V2"
        profile.migration_status = "CUTOVER_COMPLETE"
        profile.shadow_digest = comparison["moduleV2Digest"]
        profile.switched_at = datetime.utcnow()
        profile.switch_reason = reason_text
        profile.version = current_version + 1
        audit_log.record_critical_in_session(
            db, "COMMERCIAL_READER_CUTOVER", f"tenant:{tenant_id}",
            detail={"reason": reason_text, **comparison}, tenant_id=int(tenant_id), resource_id=str(profile.id),
        )
        db.commit()
        from app.services.auth_service_db import invalidate_tenant_subject_caches
        invalidate_tenant_subject_caches(int(tenant_id))
        return {"tenantId": str(tenant_id), "readerVersion": "MODULE_V2", "version": int(profile.version), "comparison": comparison}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def classify_legacy_authority(legacy_state: dict) -> dict:
    """Classify migration evidence without manufacturing a module allocation."""
    source = str(legacy_state.get("authoritySource") or "")
    if source in {"PAID_ORDER", "LEGACY_PAID_ORDER"}:
        disposition = "PAID_ORDER_REVIEW_REQUIRED"
    elif source == "TRIAL":
        disposition = "TRIAL_SCOPE_REVIEW_REQUIRED"
    elif source == "CONTROLLED_EXCEPTION":
        disposition = "CONTROLLED_EXCEPTION_REVIEW_REQUIRED"
    else:
        disposition = "INSUFFICIENT_EVIDENCE"
    return {
        "authoritySource": source or "UNKNOWN",
        "disposition": disposition,
        "autoCutoverAllowed": False,
        "moduleSourcesCreated": False,
    }
