from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import combinations
import threading

import pytest
from sqlalchemy import select

from app.core.exceptions import AppException

BASE = 1000000000000000900
MODULE_FEATURE = {
    "internship": "internship",
    "graduationDesign": "graduation",
    "studentAffairs": "studentAffairs",
    "academicAffairs": "academicAffairs",
}


def _seed_tenant(tid: int, *, meta=None):
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig, Tenant
    db=get_sessionmaker()()
    try:
        db.add(Tenant(id=tid, tenant_code=f"m12-{tid}", school_name=f"M12-{tid}",
                      deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE"))
        db.add(PlatformConfig(tenant_id=tid, config_type="TENANT_META", config_key="-",
                              config_json=meta or {"status":"trial","packageCode":"trial","environment":"test"},
                              enabled=True, status="ACTIVE"))
        db.commit()
    finally: db.close()


def _sku(module: str, *, code=None):
    from app.services import commercial_catalog_service as catalog
    payload={
        "skuCode": code or f"M12-{module}", "revision":1, "name":f"{module}商品",
        "productType":"MODULE", "moduleKey":module,
        "features":{MODULE_FEATURE[module]:True,"studentProfile":True},
        "quotas":{"students":{"limit":3000,"unit":"COUNT","aggregation":"MAX"}},
        "pricePolicy":{"unitPrice":"100.00","currency":"CNY","taxTreatment":"UNSPECIFIED"},
        "lifecyclePolicyVersion":"M12-TEST-1",
    }
    published=catalog.publish_sku(payload, reason="M12测试发布商品")
    return catalog.get_sku_snapshot(published["skuCode"], published["revision"])


def _body(tid: int, snapshots):
    start=datetime.now(timezone.utc)-timedelta(minutes=1); end=start+timedelta(days=30)
    items=[]
    for n,snapshot in enumerate(snapshots,1):
        sku=snapshot.as_dict()
        items.append({"lineNo":n,"skuCode":sku["skuCode"],"skuRevision":sku["revision"],
                      "skuContentHash":snapshot.content_hash,"quantity":1,"unitPrice":"100.00",
                      "discountAmount":"0.00","netAmount":"100.00","startAt":start.isoformat(),
                      "endAt":end.isoformat(),"requestedGeneration":1})
    return {"tenantId":str(tid),"currency":"CNY","totalAmount":f"{100*len(items):.2f}",
            "items":items,"orderType":"NEW","remark":"M12分项订单验收"}


def _pay(tid: int, snapshots, key: str):
    from app.services import commercial_order_item_service as item_svc, platform_service
    created=item_svc.create_itemized_order(_body(tid,snapshots),idempotency_key=key,actor_id="0")
    return created, platform_service.order_action(created["orderNo"],"mark-paid",
        expected_version=created["version"], reason="M12分项订单支付验收")


def _mysql():
    from app.db.session import get_engine
    if get_engine().dialect.name != "mysql": pytest.skip("MySQL concurrency proof")


@pytest.mark.parametrize("round_id", range(4))
def test_m1_concurrent_publish_and_order_idempotency(db_mode, round_id):
    _mysql()
    from app.db.session import get_sessionmaker
    from app.models import CommercialOrderItem, CommercialSkuVersion, PlatformOrder, SecurityAuditLog
    from app.services import commercial_catalog_service as catalog, commercial_order_item_service as item_svc
    tid=BASE+1+round_id*10000; _seed_tenant(tid)
    sku_code=f"M12-CONCURRENT-{round_id}"
    payload={"skuCode":sku_code,"revision":1,"name":"并发商品","productType":"MODULE",
             "moduleKey":"internship","features":{"internship":True,"studentProfile":True},"quotas":{},
             "pricePolicy":{"unitPrice":"100.00","currency":"CNY","taxTreatment":"UNSPECIFIED"},
             "lifecyclePolicyVersion":"M12-TEST-1"}
    barrier=threading.Barrier(8)
    def pub(_): barrier.wait(10); return catalog.publish_sku(payload, reason="并发发布不可变商品")
    with ThreadPoolExecutor(max_workers=8) as pool: published=list(pool.map(pub,range(8)))
    assert sum(not r["replayed"] for r in published)==1
    snapshot=catalog.get_sku_snapshot(sku_code,1); body=_body(tid,[snapshot]); barrier=threading.Barrier(8)
    def create(_): barrier.wait(10); return item_svc.create_itemized_order(body,idempotency_key=f"m12-concurrent-order-{round_id}",actor_id="7")
    with ThreadPoolExecutor(max_workers=8) as pool: orders=list(pool.map(create,range(8)))
    assert len({r["orderNo"] for r in orders})==1 and sum(not r["replayed"] for r in orders)==1
    db=get_sessionmaker()()
    try:
        assert len(db.scalars(select(CommercialSkuVersion).where(CommercialSkuVersion.sku_code==sku_code)).all())==1
        assert len(db.scalars(select(PlatformOrder).where(PlatformOrder.tenant_id==tid)).all())==1
        assert len(db.scalars(select(CommercialOrderItem).where(CommercialOrderItem.tenant_id==tid)).all())==1
        assert len(db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id==0,
            SecurityAuditLog.action=="COMMERCIAL_SKU_PUBLISH",
            SecurityAuditLog.resource==f"sku:{sku_code}:1",
        )).all())==1
    finally: db.close()


def test_m1_audit_failure_rolls_back_business_and_idempotency(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import CommercialOrderItem, IdempotencyRecord, PlatformOrder
    from app.services import audit_log, commercial_order_item_service as item_svc
    tid=BASE+2; _seed_tenant(tid); snapshot=_sku("academicAffairs",code="M12-AUDIT")
    monkeypatch.setattr(audit_log,"record_critical_in_session",lambda *a,**k: (_ for _ in ()).throw(RuntimeError("audit down")))
    with pytest.raises(RuntimeError): item_svc.create_itemized_order(_body(tid,[snapshot]),idempotency_key="m12-audit-fail",actor_id="0")
    db=get_sessionmaker()()
    try:
        assert not db.scalars(select(PlatformOrder).where(PlatformOrder.tenant_id==tid)).all()
        assert not db.scalars(select(CommercialOrderItem).where(CommercialOrderItem.tenant_id==tid)).all()
        assert not db.scalars(select(IdempotencyRecord).where(IdempotencyRecord.tenant_id==tid)).all()
    finally: db.close()


def test_m2_all_16_combinations_exact_without_employment_or_api_access(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import TenantCommercialProfile
    from app.services import commercial_entitlement_authority_service as authority
    snapshots={m:_sku(m,code=f"M12-COMBO-{m}") for m in MODULE_FEATURE}
    modules=list(MODULE_FEATURE); combos=[]
    for size in range(5): combos.extend(combinations(modules,size))
    assert len(combos)==16
    for index,selected in enumerate(combos):
        tid=BASE+100+index; _seed_tenant(tid)
        if selected: _pay(tid,[snapshots[m] for m in selected],f"m12-combo-{index:02d}")
        else:
            db=get_sessionmaker()(); db.add(TenantCommercialProfile(tenant_id=tid,reader_version="MODULE_V2",migration_status="NEW_MODULE_CUSTOMER")); db.commit(); db.close()
        state=authority.commercial_state(tid)
        assert state["verified"] is True and set(state["moduleEntitlements"])==set(selected)
        for module,feature in MODULE_FEATURE.items(): assert state["features"][feature] is (module in selected)
        assert state["features"]["employment"] is False and state["features"]["apiAccess"] is False


def test_m2_cancel_one_source_keeps_sibling_and_generation_fences_old_source(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleState, TenantModuleSubscriptionSource
    from app.services import commercial_entitlement_authority_service as authority, module_subscription_service as subs
    tid=BASE+3; _seed_tenant(tid); a=_sku("internship",code="M12-I"); b=_sku("graduationDesign",code="M12-G")
    _pay(tid,[a],"m12-source-a"); _pay(tid,[b],"m12-source-b")
    db=get_sessionmaker()()
    try:
        src=db.scalars(select(TenantModuleSubscriptionSource).where(TenantModuleSubscriptionSource.tenant_id==tid,TenantModuleSubscriptionSource.module_key=="internship")).one()
        sid,version=src.id,int(src.version or 0)
    finally: db.close()
    subs.cancel_subscription_source_now(tid,sid,expected_version=version,reason="只取消岗位实习来源")
    assert authority.commercial_state(tid)["moduleEntitlements"]==["graduationDesign"]
    db=get_sessionmaker()()
    try:
        st=db.scalars(select(TenantModuleState).where(TenantModuleState.tenant_id==tid,TenantModuleState.module_key=="graduationDesign")).one()
        st.generation=2; st.lifecycle_version=int(st.lifecycle_version)+1; db.commit()
    finally: db.close()
    assert authority.commercial_state(tid)["features"]["graduation"] is False


def test_m2_existing_formal_customer_requires_shadow_match_before_reader_cutover(db_mode):
    from app.services import commercial_entitlement_authority_service as authority, module_subscription_service as subs, platform_service
    tid=BASE+4; _seed_tenant(tid)
    legacy=platform_service.create_order({"tenantId":str(tid),"packageCode":"basic","orderType":"NEW","durationDays":30,"amount":100,"remark":"旧正式合同"})
    platform_service.order_action(legacy["orderNo"],"mark-paid",expected_version=legacy["version"],reason="旧合同支付事实")
    _pay(tid,[_sku("internship",code="M12-SHADOW")],"m12-shadow")
    assert authority.commercial_state(tid)["readerVersion"]=="LEGACY"
    comparison=subs.shadow_reconcile_tenant(tid,legacy_features=authority.legacy_commercial_state_for_reconciliation(tid)["features"])
    assert comparison["matches"] is False
    with pytest.raises(AppException): subs.switch_reader_to_module_v2(tid,expected_version=0,reason="差异未解释禁止切换",legacy_features=authority.legacy_commercial_state_for_reconciliation(tid)["features"])


def test_m2_unknown_v2_ledger_and_suspended_tenant_fail_closed(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import Tenant, TenantCommercialProfile
    from app.services import commercial_entitlement_authority_service as authority, module_subscription_service as subs
    tid=BASE+5; _seed_tenant(tid); db=get_sessionmaker()(); db.add(TenantCommercialProfile(tenant_id=tid,reader_version="MODULE_V2",migration_status="CUTOVER_COMPLETE")); db.commit(); db.close()
    monkeypatch.setattr(subs,"module_projection",lambda *a,**k: (_ for _ in ()).throw(RuntimeError("ledger unavailable")))
    state=authority.commercial_state(tid); assert state["authoritySource"]=="MODULE_V2_UNAVAILABLE" and not any(state["features"].values())
    monkeypatch.undo(); tid2=BASE+6; _seed_tenant(tid2); _pay(tid2,[_sku("internship",code="M12-SUSPEND")],"m12-suspend")
    db=get_sessionmaker()(); db.get(Tenant,tid2).status="SUSPENDED"; db.commit(); db.close()
    state=authority.commercial_state(tid2); assert state["verified"] is False and state["authoritySource"]=="MODULE_V2_TENANT_INACTIVE" and not any(state["features"].values())


def test_m2_legacy_classifier_never_manufactures_sources(db_mode):
    from app.services import module_subscription_service as subs
    for source in ("PAID_ORDER","LEGACY_PAID_ORDER","TRIAL","CONTROLLED_EXCEPTION","PACKAGE_NOT_FOUND"):
        row=subs.classify_legacy_authority({"authoritySource":source})
        assert row["autoCutoverAllowed"] is False and row["moduleSourcesCreated"] is False


def test_m1_catalog_deadlock_after_audit_retries_atomically(db_mode, monkeypatch):
    """Inject 1213 after a real audit flush; verify the real MySQL rollback."""
    _mysql()
    from sqlalchemy.exc import OperationalError
    from app.db.session import get_sessionmaker
    from app.models import CommercialSkuVersion, SecurityAuditLog
    from app.services import audit_log

    original = audit_log.record_critical_in_session
    attempts = []

    def deadlock_after_first_audit(db, action, resource, **kwargs):
        original(db, action, resource, **kwargs)
        attempts.append(id(db))
        if len(attempts) == 1:
            raise OperationalError("injected after real audit", {}, Exception(1213, "deadlock"))

    monkeypatch.setattr(audit_log, "record_critical_in_session", deadlock_after_first_audit)
    _sku("internship", code="M12-RETRY-AUDIT")
    assert len(attempts) == 2
    db = get_sessionmaker()()
    try:
        assert len(db.scalars(select(CommercialSkuVersion).where(
            CommercialSkuVersion.sku_code == "M12-RETRY-AUDIT")).all()) == 1
        assert len(db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.action == "COMMERCIAL_SKU_PUBLISH",
            SecurityAuditLog.resource == "sku:M12-RETRY-AUDIT:1")).all()) == 1
    finally:
        db.close()


def test_m1_catalog_audit_outage_rolls_back_without_retry(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import CommercialSkuVersion, SecurityAuditLog
    from app.services import audit_log

    calls = []

    def audit_outage(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(audit_log, "record_critical_in_session", audit_outage)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        _sku("internship", code="M12-SKU-AUDIT-DOWN")
    assert len(calls) == 1
    db = get_sessionmaker()()
    try:
        assert not db.scalars(select(CommercialSkuVersion).where(
            CommercialSkuVersion.sku_code == "M12-SKU-AUDIT-DOWN")).all()
        assert not db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.resource == "sku:M12-SKU-AUDIT-DOWN:1")).all()
    finally:
        db.close()


def test_m1_concurrent_different_sku_content_stays_conflict(db_mode):
    _mysql()
    from app.db.session import get_sessionmaker
    from app.models import CommercialSkuVersion, SecurityAuditLog
    from app.services import commercial_catalog_service as catalog

    barrier = threading.Barrier(8)
    def publish(index):
        payload = {"skuCode": "M12-CONTENT-RACE", "revision": 1,
                   "name": f"immutable alternative {index % 2}", "productType": "MODULE",
                   "moduleKey": "internship", "features": {"internship": True},
                   "quotas": {}, "pricePolicy": {"unitPrice": "100.00", "currency": "CNY",
                   "taxTreatment": "UNSPECIFIED"}, "lifecyclePolicyVersion": "M12-TEST-1"}
        barrier.wait(10)
        try:
            return catalog.publish_sku(payload, reason="不可变商品内容竞争验收")
        except AppException as exc:
            assert exc.http_status == 409 and exc.code == "DATA_CONFLICT"
            return {"conflict": True}

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(publish, range(8)))
    successes = [row for row in results if not row.get("conflict")]
    assert len(successes) == 4 and sum(not row["replayed"] for row in successes) == 1
    assert len({row["contentHash"] for row in successes}) == 1
    db = get_sessionmaker()()
    try:
        assert len(db.scalars(select(CommercialSkuVersion).where(
            CommercialSkuVersion.sku_code == "M12-CONTENT-RACE")).all()) == 1
        assert len(db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.action == "COMMERCIAL_SKU_PUBLISH",
            SecurityAuditLog.resource == "sku:M12-CONTENT-RACE:1")).all()) == 1
    finally:
        db.close()
