"""Real DB account subjects remain attributable without changing idempotency keys."""
from sqlalchemy import select


def test_db_subject_publishes_sku_and_order_without_losing_creator_or_replay(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CommercialSkuVersion, PlatformOrder, IdempotencyRecord
    from app.services import commercial_catalog_service as catalog, module_commerce_sales_service as sales
    from tests.test_module_commerce_m12_runtime import _seed_tenant
    from tests.test_module_commerce_sales_runtime import _draft

    tid, actor = 1000000000000048001, "db-123"
    _seed_tenant(tid)
    sku = {
        "skuCode": "DB-SUBJECT-SALE", "revision": 1, "name": "真实身份商品测试",
        "productType": "MODULE", "moduleKey": "internship", "features": {"internship": True},
        "quotas": {}, "pricePolicy": {"unitPrice": "0.10", "currency": "CNY", "taxTreatment": "UNSPECIFIED"},
        "lifecyclePolicyVersion": "TEST-ONLY",
    }
    catalog.publish_sku(sku, reason="真实数据库身份发布测试", actor_id=actor)
    snapshot = catalog.get_sku_snapshot(sku["skuCode"], 1)
    order = sales.preview_sales_order(_draft(tid, [snapshot]))["order"]
    first = sales.create_sales_order(order, idempotency_key="db-subject-order-key", actor_id=actor)
    replay = sales.create_sales_order(order, idempotency_key="db-subject-order-key", actor_id=actor)
    assert replay["replayed"] and replay["orderNo"] == first["orderNo"]
    with get_sessionmaker()() as db:
        row = db.scalars(select(CommercialSkuVersion).where(CommercialSkuVersion.sku_code == sku["skuCode"])).one()
        assert row.created_by == row.updated_by == 123
        header = db.get(PlatformOrder, int(first["orderId"]))
        assert header.created_by == header.updated_by == 123
        receipts = db.scalars(select(IdempotencyRecord).where(IdempotencyRecord.tenant_id == tid)).all()
        assert len(receipts) == 1 and receipts[0].user_id == actor


def test_db_subject_refund_records_real_operator(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CommercialRefundCase
    from app.services import module_commerce_finance_service as finance
    from tests.test_module_commerce_m8_finance import _seed_order

    tid = 1000000000000048002
    order_id = _seed_order(tid)
    created = finance.request_refund(
        {"tenantId": str(tid), "orderId": str(order_id), "amount": "1.00", "currency": "CNY", "reason": "真实数据库账号申请退款测试"},
        idempotency_key="db-subject-refund-key", actor_id="db-123")
    with get_sessionmaker()() as db:
        row = db.get(CommercialRefundCase, int(created["caseId"]))
        assert row.requested_by == 123
