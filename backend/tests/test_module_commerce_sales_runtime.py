"""M3 real migrated MySQL: catalogue -> preview -> unpaid order -> renewal ledger.

Uses disposable db_mode schools, never production customers or payment providers.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
import threading

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from tests.test_module_commerce_m12_runtime import _seed_tenant, _sku

BASE = 1000000000000006100


def _draft(tid, skus, *, order_type="NEW", start=None):
    start = start or (datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=1))
    return {"tenantId":str(tid),"orderType":order_type,"remark":"隔离学校合同分项验收",
            "items":[{"skuCode":s.as_dict()["skuCode"],"skuRevision":s.as_dict()["revision"],
                      "skuContentHash":s.content_hash,"quantity":3,"unitPrice":"0.10","discountAmount":"0.01",
                      "startAt":start.isoformat(),"endAt":(start+timedelta(days=30)).isoformat()} for s in skus]}


def _count(tid, model):
    from app.db.session import get_sessionmaker
    with get_sessionmaker()() as db:
        return db.scalar(select(func.count()).select_from(model).where(model.tenant_id==tid))


def test_sales_four_module_preview_order_and_frozen_ledger_without_grants(db_mode):
    from app.models import PlatformOrder, TenantModuleSubscriptionSource
    from app.services import module_commerce_sales_service as sales
    tid=BASE+1;_seed_tenant(tid)
    skus=[_sku(k,code=f"M3-SALE-{k}") for k in ("internship","graduationDesign","studentAffairs","academicAffairs")]
    page=sales.list_sale_skus(keyword="M3-SALE",page_size=2)
    assert page["total"]==4 and len(page["items"])==2
    preview=sales.preview_sales_order(_draft(tid,skus))
    assert preview["totalAmount"]=="1.16" and preview["validationOnly"]
    assert _count(tid,PlatformOrder)==0 and _count(tid,TenantModuleSubscriptionSource)==0
    receipt=sales.create_sales_order(preview["order"],idempotency_key="m3-sale-create-one",actor_id="0")
    assert receipt["status"]=="unpaid" and not receipt["paymentRecorded"] and not receipt["rightsMaterialized"]
    assert _count(tid,PlatformOrder)==1 and _count(tid,TenantModuleSubscriptionSource)==0
    ledger=sales.list_sales_orders(str(tid),status="unpaid")
    assert ledger["total"]==1 and ledger["items"][0]["currency"]=="CNY" and ledger["items"][0]["itemCount"]==4
    detail=sales.get_sales_order(str(tid),receipt["orderId"])
    assert [r["netAmount"] for r in detail["items"]]==["0.29"]*4
    assert all(r["fulfillmentStatus"]=="PENDING" for r in detail["items"])


def test_sales_renewal_boundary_after_real_paid_item_does_not_overwrite_sources(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleSubscriptionSource
    from app.services import module_commerce_sales_service as sales, platform_service
    tid=BASE+2;_seed_tenant(tid);sku=_sku("internship",code="M3-RENEW")
    order=sales.preview_sales_order(_draft(tid,[sku]))["order"]
    created=sales.create_sales_order(order,idempotency_key="m3-renew-first",actor_id="0")
    paid=platform_service.order_action(created["orderNo"],"mark-paid",expected_version=created["version"],reason="隔离测试支付事实")
    assert not paid.get("repairTaskRequired")
    ctx=sales.get_sales_context(str(tid));end=datetime.fromisoformat(ctx["paidThrough"]["internship"].replace("Z","+00:00"))
    with pytest.raises(AppException):sales.preview_sales_order(_draft(tid,[sku],order_type="RENEW",start=end-timedelta(seconds=1)))
    renewed=sales.preview_sales_order(_draft(tid,[sku],order_type="RENEW",start=end))
    sales.create_sales_order(renewed["order"],idempotency_key="m3-renew-unpaid-next",actor_id="0")
    with get_sessionmaker()() as db:
        sources=db.scalars(select(TenantModuleSubscriptionSource).where(TenantModuleSubscriptionSource.tenant_id==tid)).all()
        assert len(sources)==1 and sales._iso(sources[0].ends_at)==ctx["paidThrough"]["internship"]
    assert sales.list_sales_orders(str(tid),status="unpaid")["total"]==1


def test_sales_context_change_between_preview_and_create_rejects_atomically(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleState, PlatformOrder, IdempotencyRecord
    from app.services import module_commerce_sales_service as sales
    tid=BASE+3;_seed_tenant(tid);sku=_sku("internship",code="M3-FENCE")
    order=sales.preview_sales_order(_draft(tid,[sku]))["order"]
    with get_sessionmaker()() as db:
        db.add(TenantModuleState(tenant_id=tid,module_key="internship",generation=2,lifecycle_version=2,data_state="FROZEN"));db.commit()
    with pytest.raises(AppException) as caught:sales.create_sales_order(order,idempotency_key="m3-fence-changed",actor_id="0")
    assert caught.value.http_status==409 and caught.value.details["salesCommandNotCommitted"] is True
    assert _count(tid,PlatformOrder)==0 and _count(tid,IdempotencyRecord)==0


def test_sales_completed_replay_survives_retirement_but_new_selection_fails(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CommercialSkuVersion, PlatformOrder
    from app.services import module_commerce_sales_service as sales
    tid=BASE+4;_seed_tenant(tid);sku=_sku("graduationDesign",code="M3-REPLAY")
    order=sales.preview_sales_order(_draft(tid,[sku]))["order"]
    first=sales.create_sales_order(order,idempotency_key="m3-replay-persist",actor_id="0")
    with get_sessionmaker()() as db:
        row=db.scalars(select(CommercialSkuVersion).where(CommercialSkuVersion.sku_code=="M3-REPLAY")).one()
        row.publish_status="RETIRED";db.commit()
    replay=sales.create_sales_order(order,idempotency_key="m3-replay-persist",actor_id="0")
    assert replay["replayed"] and replay["orderNo"]==first["orderNo"]
    with pytest.raises(AppException):sales.create_sales_order(order,idempotency_key="m3-replay-new-key",actor_id="0")
    assert _count(tid,PlatformOrder)==1
    assert sales.list_sale_skus(keyword="M3-REPLAY")["total"]==0
    assert sales.get_sales_order(str(tid),first["orderId"])["items"][0]["skuContentHash"]==sku.content_hash


def test_sales_replay_concurrency_has_one_order_and_one_create_audit(db_mode):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import PlatformOrder, SecurityAuditLog
    from app.services import module_commerce_sales_service as sales
    assert get_engine().dialect.name=="mysql"
    tid=BASE+5;_seed_tenant(tid);sku=_sku("academicAffairs",code="M3-CONCURRENT")
    order=sales.preview_sales_order(_draft(tid,[sku]))["order"];barrier=threading.Barrier(4)
    def create(_):
        barrier.wait(timeout=10)
        return sales.create_sales_order(deepcopy(order),idempotency_key="m3-concurrent-key",actor_id="0")
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(create,range(4)))
    assert len({r["orderNo"] for r in results})==1 and sum(not r["replayed"] for r in results)==1
    assert _count(tid,PlatformOrder)==1
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id==tid,SecurityAuditLog.action=="COMMERCIAL_ITEMIZED_ORDER_CREATE"))==1


def test_sales_tenant_isolation_export_audit_and_exact_xlsx(db_mode):
    from openpyxl import load_workbook
    from app.db.session import get_sessionmaker
    from app.models import Tenant, SecurityAuditLog
    from app.services import module_commerce_sales_service as sales
    tid=BASE+6;_seed_tenant(tid);_seed_tenant(tid+1);sku=_sku("studentAffairs",code="M3-XLSX")
    created=sales.create_sales_order(sales.preview_sales_order(_draft(tid,[sku]))["order"],idempotency_key="m3-xlsx-order",actor_id="0")
    with pytest.raises(AppException) as caught:sales.get_sales_order(str(tid+1),created["orderId"])
    assert caught.value.http_status==404 and sales.list_sales_orders(str(tid+1))["total"]==0
    with get_sessionmaker()() as db:
        db.get(Tenant,tid).school_name="=1+1";db.commit()
    exported=sales.export_sales_orders({"tenantId":str(tid),"status":"unpaid","reason":"核对隔离学校合同台账"})
    sheet=load_workbook(BytesIO(base64.b64decode(exported["contentBase64"]))).active
    assert sheet["A2"].value==str(tid) and sheet["A2"].data_type=="s"
    assert sheet["B2"].value=="=1+1" and sheet["B2"].data_type=="s"
    assert sheet["P2"].value=="0.29" and not exported["truncated"]
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id==tid,SecurityAuditLog.action=="COMMERCIAL_SALES_LEDGER_EXPORT"))==1


def test_sales_audit_fault_rolls_back_unpaid_order_and_idempotency(db_mode,monkeypatch):
    from app.models import PlatformOrder, IdempotencyRecord
    from app.services import audit_log, module_commerce_sales_service as sales
    tid=BASE+8;_seed_tenant(tid);sku=_sku("internship",code="M3-AUDIT-FAIL")
    order=sales.preview_sales_order(_draft(tid,[sku]))["order"]
    def fail(*args,**kwargs):raise RuntimeError("audit unavailable")
    monkeypatch.setattr(audit_log,"record_critical_in_session",fail)
    with pytest.raises(RuntimeError):sales.create_sales_order(order,idempotency_key="m3-audit-no-order",actor_id="0")
    assert _count(tid,PlatformOrder)==0 and _count(tid,IdempotencyRecord)==0
    with pytest.raises(RuntimeError):sales.export_sales_orders({"tenantId":str(tid),"reason":"核对隔离学校合同台账"})
