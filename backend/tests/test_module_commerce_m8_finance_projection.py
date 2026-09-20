from __future__ import annotations

from decimal import Decimal


BASE = 1000000000000041000


def _seed(tid: int, currencies: list[str] | None):
    from app.db.session import get_sessionmaker
    from app.models import CommercialOrderItem, PlatformOrder, Tenant

    db = get_sessionmaker()()
    try:
        db.add(Tenant(
            id=tid, tenant_code=f"m8-currency-{tid}", school_name=f"M8Currency-{tid}",
            deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE",
        ))
        order = PlatformOrder(
            tenant_id=tid, order_no=f"M8-CUR-{tid}", order_type="NEW",
            amount=Decimal("100.00"), paid_amount=Decimal("100.00"), status="paid",
        )
        db.add(order); db.flush()
        for index, currency in enumerate(currencies or [], 1):
            db.add(CommercialOrderItem(
                tenant_id=tid, order_id=int(order.id), line_no=index,
                module_key="internship" if index == 1 else "graduationDesign",
                module_generation=1, quantity=1,
                unit_price=Decimal("50.00"), discount_amount=Decimal("0.00"),
                net_amount=Decimal("50.00"), currency=currency,
                feature_snapshot_json={}, quota_snapshot_json={},
                fulfillment_status="FULFILLED",
            ))
        db.commit()
        return int(order.id)
    finally:
        db.close()


def test_m8_finance_projection_reads_frozen_item_currency(db_mode):
    from app.services import module_commerce_finance_projection_service as projection

    tid = BASE + 1
    _seed(tid, ["CNY", "CNY"])
    row = projection.list_finance_orders(tid)["items"][0]
    assert row["orderCurrency"] == "CNY"
    assert row["currencyState"] == "KNOWN"
    assert row["currencySource"] == "COMMERCIAL_ORDER_ITEM"
    assert row["currencyConflict"] is False
    assert row["financeActionAllowed"] is True


def test_m8_legacy_order_currency_is_not_guessed(db_mode):
    from app.services import module_commerce_finance_projection_service as projection

    tid = BASE + 2
    _seed(tid, [])
    row = projection.list_finance_orders(tid)["items"][0]
    assert row["orderCurrency"] is None
    assert row["currencyState"] == "LEGACY_UNSPECIFIED"
    assert row["currencySource"] == "LEGACY_UNSPECIFIED"
    assert row["currencyConflict"] is False
    assert row["financeActionAllowed"] is True


def test_m8_mixed_currency_order_is_visible_but_finance_action_is_blocked(db_mode):
    from app.services import module_commerce_finance_projection_service as projection

    tid = BASE + 3
    _seed(tid, ["CNY", "USD"])
    row = projection.list_finance_orders(tid)["items"][0]
    assert row["orderCurrency"] is None
    assert row["currencyState"] == "CONFLICT"
    assert row["currencyConflict"] is True
    assert row["financeActionAllowed"] is False
