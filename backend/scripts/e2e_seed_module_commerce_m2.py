"""Seed the M2 sixteen-combination commercial entitlement browser matrix.

Safety: this script accepts only a local MySQL test/e2e database and never writes
FEATURES overrides. Every positive module entitlement comes from an immutable SKU,
an itemized unpaid order, and the real mark-paid -> MODULE_V2 materialization path.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import (
    PlatformConfig,
    Role,
    Tenant,
    TenantBrandConfig,
    TenantCommercialProfile,
    User,
)
from app.services import commercial_catalog_service as catalog
from app.services import commercial_entitlement_authority_service as authority
from app.services import commercial_order_item_service as orders
from app.services import platform_service
from app.services.school_iam_authority_service import converge_school_iam_authority
from app.services.system_role_shadow_service import published_system_role_permissions
from e2e_seed_control_plane_role_projection import _browser_session, _link, _role
from e2e_seed_playwright_tenants import assert_safe_target

HEAD_SHA = str(os.environ.get("E2E_EXPECTED_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
PASSWORD = "E2eModuleCommerce@2026"
BASE_TENANT_ID = 1000000000000003000
START_AT = "2026-09-01T00:00:00Z"
END_AT = "2027-09-01T00:00:00Z"
CORE_MODULES = (
    ("internship", "internship", "岗位实习中心"),
    ("graduationDesign", "graduation", "毕业设计中心"),
    ("studentAffairs", "studentAffairs", "学工中心"),
    ("academicAffairs", "academicAffairs", "教务中心"),
)
SHARED_FEATURES = ("studentProfile", "fileUpload", "approval", "todoMessage", "auditLog")


def _sku_payload(module_key: str, feature_key: str, index: int) -> dict:
    enabled = {feature_key: True, **{key: True for key in SHARED_FEATURES}}
    return {
        "skuCode": f"E2E-M2-{module_key.upper()}",
        "revision": 1,
        "name": f"M2 E2E {module_key}",
        "productType": "MODULE",
        "moduleKey": module_key,
        "features": enabled,
        "quotas": {
            "students": {"limit": 3000 + index, "unit": "COUNT", "aggregation": "MAX"},
        },
        "pricePolicy": {"unitPrice": "100.00", "currency": "CNY", "taxTreatment": "UNSPECIFIED"},
        "lifecyclePolicyVersion": "M2-E2E-1",
    }


def _ensure_tenant_identity(db, mask: int) -> tuple[Tenant, User]:
    tenant_id = BASE_TENANT_ID + mask
    code = f"m2-commerce-{mask:02d}"
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(
            id=tenant_id,
            tenant_code=code,
            school_name=f"M2商业授权组合学校{mask:02d}",
            short_name=f"M2组合{mask:02d}",
            deploy_mode="SAAS",
            db_mode="SHARED",
            status="ACTIVE",
        )
        db.add(tenant)
    else:
        if tenant.tenant_code != code:
            raise RuntimeError(f"tenant id collision for {tenant_id}")
        tenant.status = "ACTIVE"
        tenant.is_deleted = False

    meta = db.scalars(select(PlatformConfig).where(
        PlatformConfig.tenant_id == tenant_id,
        PlatformConfig.config_type == "TENANT_META",
        PlatformConfig.config_key == "-",
        PlatformConfig.is_deleted.is_(False),
    )).first()
    trial = {"status": "trial", "packageCode": "trial", "environment": "e2e"}
    if meta is None:
        db.add(PlatformConfig(
            tenant_id=tenant_id, config_type="TENANT_META", config_key="-",
            config_json=trial, enabled=True, status="ACTIVE",
        ))
    else:
        meta.config_json = trial
        meta.enabled = True
        meta.status = "ACTIVE"
        meta.is_deleted = False

    brand = db.scalars(select(TenantBrandConfig).where(TenantBrandConfig.tenant_id == tenant_id)).first()
    if brand is None:
        db.add(TenantBrandConfig(
            tenant_id=tenant_id,
            platform_name="跃科学生全生命周期平台",
            browser_title=f"M2组合{mask:02d}",
            primary_color="#2563EB",
            default_theme="academy_blue",
            watermark_text=f"M2组合{mask:02d} · E2E",
        ))

    login_name = f"m2_admin_{mask:02d}"
    user = db.scalars(select(User).where(
        User.tenant_id == tenant_id,
        User.login_name == login_name,
        User.is_deleted.is_(False),
    )).first()
    if user is None:
        user = User(
            tenant_id=tenant_id,
            login_name=login_name,
            real_name=f"M2组合管理员{mask:02d}",
            password_hash=hash_password(PASSWORD),
            user_type="ADMIN",
            status="ACTIVE",
            must_change_password=False,
        )
        db.add(user)
    else:
        user.password_hash = hash_password(PASSWORD)
        user.status = "ACTIVE"
        user.is_deleted = False
        user.must_change_password = False
    db.flush()
    role = _role(db, tenant_id, "SCHOOL_ADMIN", "学校管理员", "SYSTEM")
    _link(db, tenant_id, int(user.id), role)
    return tenant, user


def _publish_skus() -> dict[str, dict]:
    result = {}
    for index, (module_key, feature_key, _label) in enumerate(CORE_MODULES, start=1):
        payload = _sku_payload(module_key, feature_key, index)
        published = catalog.publish_sku(payload, reason="M2十六组合浏览器验收商品", actor_id=None)
        snapshot = catalog.get_sku_snapshot(published["skuCode"], published["revision"])
        result[module_key] = {
            "skuCode": published["skuCode"],
            "skuRevision": published["revision"],
            "skuContentHash": published["contentHash"],
            "snapshot": snapshot.as_dict(),
        }
    return result


def _activate_mask(mask: int, skus: dict[str, dict]) -> list[str]:
    tenant_id = BASE_TENANT_ID + mask
    selected = [module_key for index, (module_key, _feature, _label) in enumerate(CORE_MODULES) if mask & (1 << index)]
    if not selected:
        db = get_sessionmaker()()
        try:
            existing = db.scalars(select(TenantCommercialProfile).where(
                TenantCommercialProfile.tenant_id == tenant_id,
                TenantCommercialProfile.is_deleted.is_(False),
            )).first()
            if existing is None:
                db.add(TenantCommercialProfile(
                    tenant_id=tenant_id,
                    reader_version="MODULE_V2",
                    migration_status="NEW_MODULE_CUSTOMER",
                    switched_at=datetime.utcnow(),
                    switch_reason="M2 zero-module E2E baseline",
                ))
            else:
                existing.reader_version = "MODULE_V2"
                existing.migration_status = "NEW_MODULE_CUSTOMER"
            db.commit()
        finally:
            db.close()
        return selected

    item_rows = []
    for line_no, module_key in enumerate(selected, start=1):
        sku = skus[module_key]
        item_rows.append({
            "lineNo": line_no,
            "skuCode": sku["skuCode"],
            "skuRevision": int(sku["skuRevision"]),
            "skuContentHash": sku["skuContentHash"],
            "quantity": 1,
            "unitPrice": "100.00",
            "discountAmount": "0.00",
            "netAmount": "100.00",
            "startAt": START_AT,
            "endAt": END_AT,
            "requestedGeneration": 1,
        })
    created = orders.create_itemized_order({
        "tenantId": str(tenant_id),
        "currency": "CNY",
        "totalAmount": f"{len(item_rows) * 100:.2f}",
        "items": item_rows,
        "orderType": "NEW",
        "remark": f"M2 browser combination {mask:02d}",
    }, idempotency_key=f"m2-browser-combo-{mask:02d}-order", actor_id="0")
    paid = platform_service.order_action(
        created["orderNo"], "mark-paid",
        expected_version=int(created["version"]),
        reason="M2十六组合真实支付授权验收",
    )
    if paid.get("repairTaskRequired"):
        raise RuntimeError(f"M2 source materialization requires repair for mask={mask}: {paid}")
    state = authority.commercial_state(tenant_id)
    if not state.get("verified") or state.get("readerVersion") != "MODULE_V2":
        raise RuntimeError(f"M2 authority did not verify for mask={mask}: {state}")
    if set(state.get("moduleEntitlements") or []) != set(selected):
        raise RuntimeError(f"M2 module set mismatch mask={mask}: {state.get('moduleEntitlements')} != {selected}")
    if state["features"].get("employment") or state["features"].get("apiAccess"):
        raise RuntimeError(f"M2 implicit add-on grant detected mask={mask}")
    return selected


def main() -> int:
    assert_safe_target()
    if len(HEAD_SHA) < 7:
        raise SystemExit("E2E_EXPECTED_SHA/GITHUB_SHA is required")

    converge_school_iam_authority(
        source="MODULE_COMMERCE_M2_E2E",
        source_commit_sha=HEAD_SHA,
        actor_user_id=None,
    )

    db = get_sessionmaker()()
    users: dict[int, User] = {}
    try:
        for mask in range(16):
            _tenant, user = _ensure_tenant_identity(db, mask)
            users[mask] = user
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    skus = _publish_skus()
    selected_by_mask = {mask: _activate_mask(mask, skus) for mask in range(16)}

    db = get_sessionmaker()()
    try:
        school_patterns = sorted(published_system_role_permissions(db, "SCHOOL_ADMIN"))
        if len(school_patterns) < 100 or "*" in school_patterns:
            raise RuntimeError("published SCHOOL_ADMIN permission authority is not explicit")
        sessions = []
        for mask in range(16):
            tenant_id = BASE_TENANT_ID + mask
            user = db.scalars(select(User).where(
                User.tenant_id == tenant_id,
                User.login_name == f"m2_admin_{mask:02d}",
                User.is_deleted.is_(False),
            )).one()
            session = _browser_session(
                db, user,
                role_code="SCHOOL_ADMIN", channel="staff", client_type="PC",
                head_sha=HEAD_SHA, patterns=school_patterns,
                session_suffix=f"m2-{mask:02d}",
            )
            state = authority.commercial_state(tenant_id)
            sessions.append({
                **session,
                "mask": mask,
                "tenantId": str(tenant_id),
                "tenantCode": f"m2-commerce-{mask:02d}",
                "selectedModules": selected_by_mask[mask],
                "commercialFeatureKeys": sorted(key for key, enabled in state["features"].items() if enabled),
            })
    finally:
        db.close()

    fixture = {
        "schemaVersion": 1,
        "card": "PLAT-M2-16-COMBINATIONS",
        "headSha": HEAD_SHA,
        "realPaidOrderItemSources": True,
        "legacyFeatureOverrideUsed": False,
        "comboCount": len(sessions),
        "modules": [module for module, _feature, _label in CORE_MODULES],
        "sessions": sessions,
    }
    target = Path(__file__).resolve().parents[2] / "e2e" / "runtime-fixtures" / "module-commerce-m2.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(fixture, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "headSha": HEAD_SHA,
        "comboCount": len(sessions),
        "legacyFeatureOverrideUsed": False,
        "status": "MODULE_COMMERCE_M2_E2E_SEEDED",
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
