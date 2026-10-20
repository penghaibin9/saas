"""Read-only M8 finance projection enrichment.

The finance transaction service deliberately keeps PlatformOrder as payment authority.
PlatformOrder has no currency column, while itemized commercial orders freeze currency
on CommercialOrderItem.  This adapter enriches list projections from those immutable
line facts without inventing a default currency and without changing finance writers.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.db.session import get_sessionmaker


def list_finance_orders(tenant_id: int, *, page: int = 1, page_size: int = 20) -> dict:
    from app.models import CommercialOrderItem
    from app.services import module_commerce_finance_service as finance

    result = finance.list_finance_orders(tenant_id, page=page, page_size=page_size)
    rows = list(result.get("items") or [])
    order_ids = [int(row["orderId"]) for row in rows if str(row.get("orderId") or "").isdigit()]
    if not order_ids:
        return result

    currencies: dict[int, set[str]] = defaultdict(set)
    db = get_sessionmaker()()
    try:
        pairs = db.execute(select(
            CommercialOrderItem.order_id,
            CommercialOrderItem.currency,
        ).where(
            CommercialOrderItem.tenant_id == int(tenant_id),
            CommercialOrderItem.order_id.in_(order_ids),
            CommercialOrderItem.currency.is_not(None),
            CommercialOrderItem.is_deleted.is_(False),
        )).all()
        for order_id, currency in pairs:
            text = str(currency or "").strip().upper()
            if text:
                currencies[int(order_id)].add(text)
    finally:
        db.close()

    enriched = []
    for row in rows:
        item = dict(row)
        values = sorted(currencies.get(int(item["orderId"]), set()))
        if len(values) == 1:
            item["orderCurrency"] = values[0]
            item["currencyState"] = "KNOWN"
            item["currencyConflict"] = False
        elif len(values) == 0:
            item["orderCurrency"] = None
            item["currencyState"] = "LEGACY_UNSPECIFIED"
            item["currencyConflict"] = False
        else:
            item["orderCurrency"] = None
            item["currencyState"] = "CONFLICT"
            item["currencyConflict"] = True
        item["currencySource"] = "COMMERCIAL_ORDER_ITEM" if values else "LEGACY_UNSPECIFIED"
        item["financeActionAllowed"] = not item["currencyConflict"]
        enriched.append(item)
    return {**result, "items": enriched}
