from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.core.exceptions import AppException

BASE = 1000000000000038000


def _seed_order(tid: int, *, amount="100.00", paid="100.00", status="paid", active_source=False):
    from app.db.session import get_sessionmaker
    from app.models import (
        CommercialOrderItem, PlatformOrder, Tenant, TenantModuleState,
        TenantModuleSubscriptionSource,
    )

    db = get_sessionmaker()()
    try:
        db.add(Tenant(
            id=tid, tenant_code=f"m8-fin-{tid}", school_name=f"M8Finance-{tid}",
            deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE",
        ))
        order = PlatformOrder(
            tenant_id=tid, order_no=f"M8-{tid}", order_type="NEW",
            amount=Decimal(amount), paid_amount=Decimal(paid), status=status,
            start_at=datetime.utcnow(), end_at=datetime.utcnow() + timedelta(days=365),
            remark="M8 finance test order",
        )
        db.add(order); db.flush()
        item = CommercialOrderItem(
            tenant_id=tid, order_id=int(order.id), line_no=1,
            sku_code="internship-standard", sku_revision=1,
            sku_content_hash="a" * 64, module_key="internship", module_generation=1,
            quantity=1, unit_price=Decimal(amount), discount_amount=Decimal("0.00"),
            net_amount=Decimal(amount), currency="CNY",
            service_start_at=datetime.utcnow(), service_end_at=datetime.utcnow() + timedelta(days=365),
            sku_snapshot_json={"skuCode": "internship-standard", "revision": 1, "moduleKey": "internship"},
            feature_snapshot_json={"internship": True}, quota_snapshot_json={},
            fulfillment_status="FULFILLED",
        )
        db.add(item); db.flush()
        if active_source:
            db.add(TenantModuleState(
                tenant_id=tid, module_key="internship", generation=1,
                lifecycle_version=1, data_state="AVAILABLE",
            ))
            db.add(TenantModuleSubscriptionSource(
                tenant_id=tid, module_key="internship", module_generation=1,
                source_type="PAID_ORDER_ITEM", source_ref=f"ORDER_ITEM:{item.id}",
                order_item_id=int(item.id), feature_snapshot_json={"internship": True},
                quota_snapshot_json={}, starts_at=datetime.utcnow() - timedelta(days=1),
                ends_at=datetime.utcnow() + timedelta(days=364), status="ACTIVE",
                approval_ref="M8-TEST", activated_at=datetime.utcnow(),
            ))
        db.commit()
        return int(order.id)
    finally:
        db.close()


def test_m8_receivable_is_derived_from_platform_order_without_second_balance_table(db_mode):
    from app.services import module_commerce_finance_service as finance

    tid = BASE + 1
    order_id = _seed_order(tid, amount="120.00", paid="70.00")
    result = finance.list_finance_orders(tid)
    assert result["total"] == 1
    row = result["items"][0]
    assert row["orderId"] == str(order_id)
    assert row["amount"] == "120.00"
    assert row["paidAmount"] == "70.00"
    assert row["outstandingAmount"] == "50.00"
    assert row["paymentAuthority"] == "PLATFORM_ORDER"
    assert row["receivableDerivedNotDuplicated"] is True


def test_m8_refund_idempotency_and_payload_collision_are_fail_closed(db_mode):
    from app.services import module_commerce_finance_service as finance

    tid = BASE + 2
    order_id = _seed_order(tid)
    body = {"tenantId": str(tid), "orderId": str(order_id), "amount": "25.00", "currency": "CNY", "reason": "学校确认退回未使用服务费用"}
    first = finance.request_refund(body, idempotency_key="refund-command-0001", actor_id=71)
    replay = finance.request_refund(body, idempotency_key="refund-command-0001", actor_id=71)
    assert first["replayed"] is False
    assert replay["replayed"] is True
    assert first["caseId"] == replay["caseId"]
    with pytest.raises(AppException) as caught:
        finance.request_refund({**body, "amount": "20.00"}, idempotency_key="refund-command-0001", actor_id=71)
    assert caught.value.http_status == 409


def test_m8_approved_refunds_reserve_balance_and_second_approval_rechecks_under_lock(db_mode):
    from app.services import module_commerce_finance_service as finance

    tid = BASE + 3
    order_id = _seed_order(tid)
    first = finance.request_refund({"tenantId": str(tid), "orderId": str(order_id), "amount": "60.00", "currency": "CNY", "reason": "第一笔退款申请用于并发额度复核"}, idempotency_key="refund-capacity-001", actor_id=72)
    # REQUESTED cases do not reserve money; both may enter review before either is approved.
    second = finance.request_refund({"tenantId": str(tid), "orderId": str(order_id), "amount": "50.00", "currency": "CNY", "reason": "第二笔退款申请用于锁内重新核算"}, idempotency_key="refund-capacity-002", actor_id=72)
    approved = finance.approve_refund(tid, first["caseId"], expected_version=first["version"], note="合同与财务复核通过", actor_id=73)
    assert approved["status"] == "APPROVED"
    with pytest.raises(AppException) as caught:
        finance.approve_refund(tid, second["caseId"], expected_version=second["version"], note="再次复核退款额度", actor_id=73)
    assert caught.value.http_status == 409
    assert caught.value.details["availableAmount"] == "40.00"


def test_m8_invoice_and_refund_share_one_paid_cash_capacity_and_void_releases_it(db_mode):
    from app.services import module_commerce_finance_service as finance

    tid = BASE + 4
    order_id = _seed_order(tid)
    invoice = finance.request_invoice({"tenantId": str(tid), "orderId": str(order_id), "amount": "40.00", "currency": "CNY", "invoiceTitle": "湖南测试职业学校"}, idempotency_key="invoice-command-001", actor_id=74)
    issued = finance.issue_invoice(tid, invoice["invoiceCaseId"], expected_version=invoice["version"], external_invoice_ref="INV-EXT-2026-0001", actor_id=75)
    assert issued["status"] == "ISSUED"
    with pytest.raises(AppException) as caught:
        finance.request_refund({"tenantId": str(tid), "orderId": str(order_id), "amount": "70.00", "currency": "CNY", "reason": "已开票四十后七十退款应先处理发票"}, idempotency_key="refund-after-invoice-1", actor_id=74)
    assert caught.value.http_status == 409
    voided = finance.void_invoice(tid, issued["invoiceCaseId"], expected_version=issued["version"], reason="客户确认原发票已在外部渠道作废", actor_id=75)
    assert voided["status"] == "VOIDED"
    refund = finance.request_refund({"tenantId": str(tid), "orderId": str(order_id), "amount": "70.00", "currency": "CNY", "reason": "发票作废后重新申请七十元退款"}, idempotency_key="refund-after-invoice-2", actor_id=74)
    assert refund["status"] == "REQUESTED"


def test_m8_settlement_records_external_evidence_without_mutating_order_or_entitlement(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import PlatformOrder, TenantModuleSubscriptionSource
    from app.services import module_commerce_finance_service as finance

    tid = BASE + 5
    order_id = _seed_order(tid, active_source=True)
    case = finance.request_refund({"tenantId": str(tid), "orderId": str(order_id), "amount": "30.00", "currency": "CNY", "reason": "学校已确认退款范围并保留授权人工复核"}, idempotency_key="refund-settle-001", actor_id=76)
    approved = finance.approve_refund(tid, case["caseId"], expected_version=case["version"], note="退款额度审批通过", actor_id=77)
    settled = finance.settle_refund(tid, approved["caseId"], expected_version=approved["version"], settlement_ref="BANK-REFUND-2026-00001", actor_id=78)
    assert settled["status"] == "SETTLED"
    assert settled["externalRefundExecutedBySystem"] is False
    assert settled["orderStatusChanged"] is False
    assert settled["entitlementImpact"]["entitlementChangeApplied"] is False
    assert settled["entitlementImpact"]["followUpRequired"] is True
    assert settled["entitlementImpact"]["activeEntitlementSourceCount"] == 1
    db = get_sessionmaker()()
    try:
        from sqlalchemy import select
        order = db.scalars(select(PlatformOrder).where(PlatformOrder.id == order_id, PlatformOrder.tenant_id == tid)).first()
        source = db.scalars(select(TenantModuleSubscriptionSource).where(TenantModuleSubscriptionSource.tenant_id == tid)).first()
        assert order.status == "paid"
        assert Decimal(str(order.paid_amount)) == Decimal("100.00")
        assert source.status == "ACTIVE"
    finally:
        db.close()


def test_m8_legacy_order_already_marked_refunded_cannot_start_second_refund_or_invoice(db_mode):
    from app.services import module_commerce_finance_service as finance

    tid = BASE + 6
    order_id = _seed_order(tid, status="refunded")
    with pytest.raises(AppException) as refund_error:
        finance.request_refund({"tenantId": str(tid), "orderId": str(order_id), "amount": "10.00", "currency": "CNY", "reason": "历史已退款订单不得再次退款"}, idempotency_key="legacy-refunded-rf", actor_id=79)
    assert refund_error.value.http_status == 409
    with pytest.raises(AppException) as invoice_error:
        finance.request_invoice({"tenantId": str(tid), "orderId": str(order_id), "amount": "10.00", "currency": "CNY", "invoiceTitle": "历史已退款学校"}, idempotency_key="legacy-refunded-iv", actor_id=79)
    assert invoice_error.value.http_status == 409


def test_m8_refund_request_rolls_back_business_fact_when_critical_audit_fails(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import CommercialRefundCase
    from app.services import audit_log
    from app.services import module_commerce_finance_service as finance
    from sqlalchemy import func, select

    tid = BASE + 7
    order_id = _seed_order(tid)
    monkeypatch.setattr(audit_log, "record_critical_in_session", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("audit unavailable")))
    with pytest.raises(RuntimeError):
        finance.request_refund({"tenantId": str(tid), "orderId": str(order_id), "amount": "10.00", "currency": "CNY", "reason": "审计失败时退款事实不得提交"}, idempotency_key="refund-audit-fail", actor_id=80)
    db = get_sessionmaker()()
    try:
        assert int(db.scalar(select(func.count(CommercialRefundCase.id)).where(CommercialRefundCase.tenant_id == tid)) or 0) == 0
    finally:
        db.close()
