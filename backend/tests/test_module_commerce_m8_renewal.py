from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from decimal import Decimal
import pytest
BASE=1000000000000045000

def _seed_source(tid,*,module_key="internship",ends_in_days=30,status="ACTIVE",extra_later_source=False):
    from app.db.session import get_sessionmaker
    from app.models import CommercialOrderItem,PlatformOrder,Tenant,TenantModuleState,TenantModuleSubscriptionSource
    db=get_sessionmaker()()
    try:
        db.add(Tenant(id=tid,tenant_code=f"m8-renew-{tid}",school_name=f"M8Renew-{tid}",deploy_mode="SAAS",db_mode="SHARED",status="ACTIVE"))
        db.add(TenantModuleState(tenant_id=tid,module_key=module_key,generation=1,lifecycle_version=1,data_state="AVAILABLE"))
        order=PlatformOrder(tenant_id=tid,order_no=f"M8-RENEW-{tid}",order_type="NEW",package_code="MODULE_V2",amount=Decimal("100.00"),paid_amount=Decimal("100.00"),status="paid"); db.add(order); db.flush()
        item=CommercialOrderItem(tenant_id=tid,order_id=int(order.id),line_no=1,module_key=module_key,module_generation=1,sku_code="YK-INTERNSHIP",sku_revision=1,sku_content_hash="a"*64,quantity=1,unit_price=Decimal("100.00"),discount_amount=Decimal("0.00"),net_amount=Decimal("100.00"),currency="CNY",service_start_at=datetime.utcnow()-timedelta(days=335),service_end_at=datetime.utcnow()+timedelta(days=ends_in_days),feature_snapshot_json={module_key:True},quota_snapshot_json={},fulfillment_status="FULFILLED"); db.add(item); db.flush()
        source=TenantModuleSubscriptionSource(tenant_id=tid,module_key=module_key,module_generation=1,source_type="PAID_ORDER_ITEM",source_ref=f"ORDER_ITEM:{item.id}:1",order_item_id=int(item.id),feature_snapshot_json={module_key:True},quota_snapshot_json={},starts_at=datetime.utcnow()-timedelta(days=335),ends_at=datetime.utcnow()+timedelta(days=ends_in_days),status=status,approval_ref="M8-RENEW",activated_at=datetime.utcnow()); db.add(source); db.flush(); later_id=None
        if extra_later_source:
            later=TenantModuleSubscriptionSource(tenant_id=tid,module_key=module_key,module_generation=1,source_type="PAID_ORDER_ITEM",source_ref=f"ORDER_ITEM:{item.id}:2",order_item_id=int(item.id),feature_snapshot_json={module_key:True},quota_snapshot_json={},starts_at=datetime.utcnow()+timedelta(days=ends_in_days),ends_at=datetime.utcnow()+timedelta(days=ends_in_days+365),status="SCHEDULED",approval_ref="M8-RENEW-LATER"); db.add(later); db.flush(); later_id=int(later.id)
        db.commit(); return int(source.id),later_id
    finally: db.close()

def test_m8_renewal_candidates_only_surface_terminal_paid_source(db_mode):
    from app.services import module_commerce_renewal_service as renewal
    tid=BASE+1; old_id,latest_id=_seed_source(tid,ends_in_days=20,extra_later_source=True); data=renewal.list_renewal_candidates(tid,within_days=500); assert data["projectionRule"]=="LATEST_PAID_SOURCE_PER_MODULE_GENERATION"; assert data["total"]==1; row=data["items"][0]; assert row["sourceId"]==str(latest_id) and row["sourceId"]!=str(old_id); assert row["canCreateFollowup"] is True; assert row["renewalOrderInput"]["orderType"]=="RENEW"; assert row["renewalOrderInput"]["priceMustBeReconfirmed"] is True; assert row["renewalOrderInput"]["endAtMustBeExplicit"] is True

def test_m8_renewal_followup_reuses_customer_success_task_and_never_creates_order(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CommercialRenewalFollowupLink,PlatformOrder
    from app.models.customer_success import RenewalTask
    from app.services import module_commerce_renewal_service as renewal
    from sqlalchemy import func,select
    tid=BASE+2; source_id,_=_seed_source(tid); first=renewal.ensure_renewal_followup({"userId":"91"},tid,source_id,due_at="2026-09-20T00:00:00Z",owner_name="客户成功A",note="在服务期结束前完成合同续费沟通和正式报价确认"); replay=renewal.ensure_renewal_followup({"userId":"91"},tid,source_id,due_at="2026-09-25T00:00:00Z",owner_name="不会覆盖",note="重复提交只能找回原客户成功续费任务"); assert first["replayed"] is False and replay["replayed"] is True; assert replay["renewalTask"]["taskId"]==first["renewalTask"]["taskId"]; assert first["automaticRenewalExecuted"] is False and first["paymentExecuted"] is False and first["entitlementChangeApplied"] is False
    db=get_sessionmaker()()
    try:
        assert int(db.scalar(select(func.count(RenewalTask.id)).where(RenewalTask.tenant_id==tid)) or 0)==1; assert int(db.scalar(select(func.count(CommercialRenewalFollowupLink.id)).where(CommercialRenewalFollowupLink.tenant_id==tid)) or 0)==1; assert int(db.scalar(select(func.count(PlatformOrder.id)).where(PlatformOrder.tenant_id==tid,PlatformOrder.order_type=="RENEW",PlatformOrder.is_deleted.is_(False))) or 0)==0
    finally: db.close()
    after=renewal.list_renewal_candidates(tid)["items"][0]; assert after["renewalTask"]["status"]=="PENDING" and after["canStartRenewalOrder"] is True and after["canCreateFollowup"] is False

def test_m8_stop_renew_source_visible_but_cannot_create_followup(db_mode):
    from app.services import module_commerce_renewal_service as renewal
    tid=BASE+3; source_id,_=_seed_source(tid,status="CANCEL_SCHEDULED"); row=renewal.list_renewal_candidates(tid)["items"][0]; assert row["sourceId"]==str(source_id) and row["canCreateFollowup"] is False and row["blocker"]["code"]=="STOP_RENEW_SCHEDULED"
    with pytest.raises(Exception) as exc: renewal.ensure_renewal_followup({"userId":"93"},tid,source_id,due_at="2026-09-20T00:00:00Z",owner_name="客户成功",note="已停续来源不能绕过撤销停续直接创建续费任务")
    assert getattr(exc.value,"http_status",None)==409

def test_m8_old_paid_source_cannot_race_newer_paid_boundary(db_mode):
    from app.services import module_commerce_renewal_service as renewal
    tid=BASE+4; old_id,latest_id=_seed_source(tid,ends_in_days=10,extra_later_source=True); assert latest_id
    with pytest.raises(Exception) as exc: renewal.ensure_renewal_followup({"userId":"94"},tid,old_id,due_at="2026-09-20T00:00:00Z",owner_name="客户成功",note="旧来源已经不是最晚已付边界，必须刷新后再办理续费")
    assert getattr(exc.value,"http_status",None)==409

def test_m8_concurrent_renewal_followup_creates_one_task_and_link(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CommercialRenewalFollowupLink
    from app.models.customer_success import RenewalTask
    from app.services import module_commerce_renewal_service as renewal
    from sqlalchemy import func,select
    tid=BASE+5; source_id,_=_seed_source(tid)
    def worker(): return renewal.ensure_renewal_followup({"userId":"95"},tid,source_id,due_at="2026-09-20T00:00:00Z",owner_name="客户成功",note="并发重试只能产生一个正式续费跟进任务和一个来源关联")
    with ThreadPoolExecutor(max_workers=2) as pool: results=[future.result(timeout=20) for future in (pool.submit(worker),pool.submit(worker))]
    assert len({row["renewalTask"]["taskId"] for row in results})==1 and sorted(row["replayed"] for row in results)==[False,True]
    db=get_sessionmaker()()
    try:
        assert int(db.scalar(select(func.count(RenewalTask.id)).where(RenewalTask.tenant_id==tid)) or 0)==1; assert int(db.scalar(select(func.count(CommercialRenewalFollowupLink.id)).where(CommercialRenewalFollowupLink.tenant_id==tid)) or 0)==1
    finally: db.close()

def test_m8_renewal_link_audit_failure_rolls_back_task_and_link(db_mode,monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import CommercialRenewalFollowupLink
    from app.models.customer_success import RenewalTask
    from app.services import audit_log,module_commerce_renewal_service as renewal
    from sqlalchemy import func,select
    tid=BASE+6; source_id,_=_seed_source(tid); original=audit_log.record_critical_in_session; calls={"n":0}
    def fail_second(*args,**kwargs):
        calls["n"]+=1
        if calls["n"]==2: raise RuntimeError("audit unavailable")
        return original(*args,**kwargs)
    monkeypatch.setattr(audit_log,"record_critical_in_session",fail_second)
    with pytest.raises(RuntimeError): renewal.ensure_renewal_followup({"userId":"96"},tid,source_id,due_at="2026-09-20T00:00:00Z",owner_name="客户成功",note="商业续费关联审计失败时任务和关联必须一起回滚")
    db=get_sessionmaker()()
    try:
        assert int(db.scalar(select(func.count(RenewalTask.id)).where(RenewalTask.tenant_id==tid)) or 0)==0; assert int(db.scalar(select(func.count(CommercialRenewalFollowupLink.id)).where(CommercialRenewalFollowupLink.tenant_id==tid)) or 0)==0
    finally: db.close()
