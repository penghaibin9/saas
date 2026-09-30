from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

BASE = 1000000000000043000


def _seed_refund(tid: int, *, active_source: bool = True):
    from app.db.session import get_sessionmaker
    from app.models import (
        CommercialOrderItem, CommercialRefundCase, PlatformOrder, Tenant,
        TenantModuleState, TenantModuleSubscriptionSource,
    )

    db = get_sessionmaker()()
    try:
        db.add(Tenant(
            id=tid, tenant_code=f"m8-ops-{tid}", school_name=f"M8Ops-{tid}",
            deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE",
        ))
        order = PlatformOrder(
            tenant_id=tid, order_no=f"M8-OPS-{tid}", order_type="NEW",
            amount=Decimal("100.00"), paid_amount=Decimal("100.00"), status="paid",
        )
        db.add(order); db.flush()
        item = CommercialOrderItem(
            tenant_id=tid, order_id=int(order.id), line_no=1,
            module_key="internship", module_generation=1, quantity=1,
            unit_price=Decimal("100.00"), discount_amount=Decimal("0.00"),
            net_amount=Decimal("100.00"), currency="CNY",
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
                quota_snapshot_json={}, starts_at=datetime.utcnow() - timedelta(days=2),
                ends_at=datetime.utcnow() + timedelta(days=300), status="ACTIVE",
                approval_ref="M8-OPS", activated_at=datetime.utcnow(),
            ))
        refund = CommercialRefundCase(
            tenant_id=tid, order_id=int(order.id), case_no=f"RF-M8OPS-{tid}",
            request_key_hash=("a" * 48 + f"{tid % 10:01d}" * 16)[:64],
            request_payload_hash="b" * 64, amount=Decimal("30.00"), currency="CNY",
            order_paid_amount_snapshot=Decimal("100.00"), reason="学校确认外部退款事实",
            status="SETTLED", requested_at=datetime.utcnow() - timedelta(hours=2),
            approved_at=datetime.utcnow() - timedelta(hours=1),
            settled_at=datetime.utcnow(), settlement_ref=f"BANK-M8-{tid}",
        )
        db.add(refund); db.commit(); db.refresh(refund)
        return int(order.id), int(refund.id)
    finally:
        db.close()


def test_m8_settled_refund_creates_one_existing_customer_success_ticket_and_replays(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CommercialAfterSalesLink, TenantModuleSubscriptionSource
    from app.models.customer_success import SupportTicket
    from app.services import module_commerce_operations_service as ops
    from sqlalchemy import func, select

    tid = BASE + 1
    _, refund_id = _seed_refund(tid)
    first = ops.ensure_refund_after_sales_ticket(
        {"userId": "81"}, tid, refund_id, severity="P2",
        reason="退款完成后复核当前实习模块授权是否应继续保留",
    )
    replay = ops.ensure_refund_after_sales_ticket(
        {"userId": "81"}, tid, refund_id, severity="P1",
        reason="重复请求不得生成第二张售后工单",
    )
    assert first["ticketCreated"] is True
    assert first["followUpRequired"] is True
    assert first["entitlementChangeApplied"] is False
    assert first["moduleSnapshot"] == [{"moduleKey": "internship", "sourceCount": 1}]
    assert replay["replayed"] is True
    assert replay["supportTicketId"] == first["supportTicketId"]
    assert replay["sla"]["status"] == "UNASSESSED"
    assert replay["sla"]["policyConfigured"] is False

    db = get_sessionmaker()()
    try:
        assert int(db.scalar(select(func.count(SupportTicket.id)).where(SupportTicket.tenant_id == tid)) or 0) == 1
        assert int(db.scalar(select(func.count(CommercialAfterSalesLink.id)).where(CommercialAfterSalesLink.tenant_id == tid)) or 0) == 1
        source = db.scalars(select(TenantModuleSubscriptionSource).where(TenantModuleSubscriptionSource.tenant_id == tid)).one()
        assert source.status == "ACTIVE"
    finally:
        db.close()


def test_m8_concurrent_after_sales_retries_serialize_on_refund_row(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.customer_success import SupportTicket
    from app.services import module_commerce_operations_service as ops
    from sqlalchemy import func, select

    tid = BASE + 2
    _, refund_id = _seed_refund(tid)

    def worker():
        return ops.ensure_refund_after_sales_ticket(
            {"userId": "82"}, tid, refund_id, severity="P2",
            reason="并发重试必须只生成一张退款后授权复核工单",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=20) for future in [pool.submit(worker), pool.submit(worker)]]
    assert len({row["supportTicketId"] for row in results}) == 1
    assert sorted(row["replayed"] for row in results) == [False, True]
    db = get_sessionmaker()()
    try:
        assert int(db.scalar(select(func.count(SupportTicket.id)).where(SupportTicket.tenant_id == tid)) or 0) == 1
    finally:
        db.close()


def test_m8_no_active_entitlement_does_not_manufacture_support_ticket(db_mode):
    from app.services import module_commerce_operations_service as ops

    tid = BASE + 3
    _, refund_id = _seed_refund(tid, active_source=False)
    result = ops.ensure_refund_after_sales_ticket(
        {"userId": "83"}, tid, refund_id, severity="P2",
        reason="没有有效授权来源时只记录无需跟进结论",
    )
    assert result["followUpRequired"] is False
    assert result["ticketCreated"] is False
    assert result["entitlementChangeApplied"] is False


def test_m8_sla_is_unassessed_without_policy_and_breached_only_after_explicit_policy(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig
    from app.models.customer_success import SupportTicket
    from app.services import module_commerce_operations_service as ops

    tid = BASE + 4
    _, refund_id = _seed_refund(tid)
    linked = ops.ensure_refund_after_sales_ticket(
        {"userId": "84"}, tid, refund_id, severity="P2",
        reason="用于显式SLA策略验收",
    )
    before = ops.list_after_sales(tid)["items"][0]
    assert before["sla"]["status"] == "UNASSESSED"
    assert before["sla"]["targetHours"] is None

    db = get_sessionmaker()()
    try:
        ticket = db.get(SupportTicket, int(linked["supportTicketId"]))
        ticket.created_at = datetime.utcnow() - timedelta(hours=3)
        db.add(PlatformConfig(
            tenant_id=tid, config_type="COMMERCIAL_SLA_POLICY", config_key="SUPPORT_TICKET",
            config_json={"version": "SLA-CONTRACT-2026-09", "targetsHours": {"P2": 2}},
            enabled=True, status="ACTIVE",
        ))
        db.commit()
    finally:
        db.close()
    after = ops.list_after_sales(tid)["items"][0]
    assert after["sla"]["policyConfigured"] is True
    assert after["sla"]["policyVersion"] == "SLA-CONTRACT-2026-09"
    assert after["sla"]["targetHours"] == 2.0
    assert after["sla"]["status"] == "BREACHED"


def test_m8_actual_cost_is_idempotent_and_never_cross_currency_summed(db_mode):
    from app.services import module_commerce_operations_service as ops

    tid = BASE + 5
    order_id, refund_id = _seed_refund(tid)
    linked = ops.ensure_refund_after_sales_ticket(
        {"userId": "85"}, tid, refund_id, severity="P2",
        reason="成本事实绑定现有售后工单",
    )
    cny_body = {
        "costType": "SUPPORT", "amount": "12.50", "currency": "CNY",
        "occurredAt": "2026-09-09T10:00:00Z", "supportTicketId": linked["supportTicketId"],
        "refundCaseId": str(refund_id), "orderId": str(order_id),
        "externalRef": "COST-CNY-001", "note": "远程支持实际人工成本",
    }
    first = ops.record_service_cost({"userId": "85"}, tid, cny_body, idempotency_key="m8-cost-cny-0001")
    replay = ops.record_service_cost({"userId": "85"}, tid, cny_body, idempotency_key="m8-cost-cny-0001")
    assert first["replayed"] is False and replay["replayed"] is True
    ops.record_service_cost({"userId": "85"}, tid, {
        "costType": "REFUND_FEE", "amount": "2.00", "currency": "USD",
        "occurredAt": "2026-09-09T11:00:00Z", "refundCaseId": str(refund_id),
        "externalRef": "COST-USD-001", "note": "外部渠道实际手续费",
    }, idempotency_key="m8-cost-usd-0001")
    ledger = ops.list_service_costs(tid)
    assert ledger["currencyConverted"] is False
    assert ledger["summaryByCurrency"]["CNY"] == [{"costType": "SUPPORT", "amount": "12.50", "count": 1}]
    assert ledger["summaryByCurrency"]["USD"] == [{"costType": "REFUND_FEE", "amount": "2.00", "count": 1}]


def test_m8_operations_overview_surfaces_refund_review_training_renewal_and_delivery_facts(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig
    from app.models.customer_success import RenewalTask, TrainingRecord
    from app.services import module_commerce_operations_service as ops

    tid = BASE + 6
    _, refund_id = _seed_refund(tid)
    db = get_sessionmaker()()
    try:
        db.add(TrainingRecord(
            tenant_id=tid, topic="商业交付培训", trainer_name="跃科",
            scheduled_at=datetime.utcnow() + timedelta(days=1), status="SCHEDULED",
        ))
        db.add(RenewalTask(
            tenant_id=tid, due_at=datetime.utcnow() + timedelta(days=30),
            status="PENDING", owner_name="客户成功",
        ))
        db.add(PlatformConfig(
            tenant_id=tid, config_type="MODULE_DELIVERY_ACCEPTANCE", config_key="internship:1:test",
            config_json={"moduleKey": "internship", "moduleGeneration": 1}, enabled=True, status="ACTIVE",
        ))
        db.commit()
    finally:
        db.close()
    before = ops.operations_overview(tid)
    assert before["pendingRefundEntitlementReviews"] == 1
    assert before["scheduledTrainings"] == 1
    assert before["openRenewalTasks"] == 1
    assert before["moduleDeliveryAcceptanceFacts"] == 1
    assert before["entitlementAutoMutation"] is False
    ops.ensure_refund_after_sales_ticket(
        {"userId": "86"}, tid, refund_id, severity="P2",
        reason="完成持续治理售后工单关联",
    )
    after = ops.operations_overview(tid)
    assert after["pendingRefundEntitlementReviews"] == 0
    assert after["openRefundAfterSalesTickets"] == 1


def test_m8_after_sales_audit_failure_rolls_back_ticket_and_link(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import CommercialAfterSalesLink
    from app.models.customer_success import SupportTicket
    from app.services import audit_log
    from app.services import module_commerce_operations_service as ops
    from sqlalchemy import func, select

    tid = BASE + 7
    _, refund_id = _seed_refund(tid)
    original = audit_log.record_critical_in_session
    calls = {"n": 0}
    def fail_second(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("audit unavailable")
        return original(*args, **kwargs)
    monkeypatch.setattr(audit_log, "record_critical_in_session", fail_second)
    with pytest.raises(RuntimeError):
        ops.ensure_refund_after_sales_ticket(
            {"userId": "87"}, tid, refund_id, severity="P2",
            reason="审计失败时工单和关联必须同事务回滚",
        )
    db = get_sessionmaker()()
    try:
        assert int(db.scalar(select(func.count(SupportTicket.id)).where(SupportTicket.tenant_id == tid)) or 0) == 0
        assert int(db.scalar(select(func.count(CommercialAfterSalesLink.id)).where(CommercialAfterSalesLink.tenant_id == tid)) or 0) == 0
    finally:
        db.close()
