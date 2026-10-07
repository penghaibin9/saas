"""MySQL receipt replay after retirement; test tenants and real order transactions."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import CommercialSkuVersion, PlatformOrder, SecurityAuditLog, TenantModuleSubscriptionSource
from app.services import commercial_order_item_service as orders, platform_service
from test_module_commerce_m12_runtime import _body, _mysql, _seed_tenant, _sku


def _retired_order(tid, code):
    _mysql()
    _seed_tenant(tid)
    sku = _sku("internship", code=code)
    body = _body(tid, [sku])
    receipt = orders.create_itemized_order(body, idempotency_key="retirement-replay-key", actor_id="7")
    paid = platform_service.order_action(receipt["orderNo"], "mark-paid",
        expected_version=receipt["version"], reason="退休回放验证测试订单付款")
    assert paid["rightsMaterialized"] is True
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(CommercialSkuVersion).where(CommercialSkuVersion.sku_code == code)).one()
        row.publish_status = "RETIRED"
        db.commit()
    finally:
        db.close()
    return body, receipt


def test_completed_order_replays_eight_times_after_retirement_and_catalogue_outage(db_mode, monkeypatch):
    tid = 1000000000000092001
    body, receipt = _retired_order(tid, "REPLAY-RETIRED-1")
    def unavailable(*args, **kwargs):
        raise AssertionError("completed command must not resolve catalogue")
    monkeypatch.setattr(orders, "get_sku_snapshot", unavailable)
    barrier = threading.Barrier(8)
    def replay(_):
        barrier.wait(10)
        return orders.create_itemized_order(body, idempotency_key="retirement-replay-key", actor_id="7")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(replay, range(8)))
    assert all(result == {**receipt, "replayed": True} for result in results)
    db = get_sessionmaker()()
    try:
        stored = db.scalars(select(PlatformOrder).where(PlatformOrder.tenant_id == tid)).all()
        assert len(stored) == 1 and stored[0].status == "paid"
        assert len(db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == tid,
            SecurityAuditLog.action == "COMMERCIAL_ITEMIZED_ORDER_CREATE")).all()) == 1
        assert len(db.scalars(select(TenantModuleSubscriptionSource).where(
            TenantModuleSubscriptionSource.tenant_id == tid)).all()) == 1
    finally:
        db.close()


@pytest.mark.parametrize("changed", ["payload", "key", "actor"])
def test_retired_catalogue_does_not_allow_conflicting_or_new_commands(db_mode, changed):
    tid = 1000000000000092010 + ["payload", "key", "actor"].index(changed)
    body, _receipt = _retired_order(tid, f"REPLAY-RETIRED-{changed.upper()}")
    key, actor = "retirement-replay-key", "7"
    if changed == "payload":
        body["remark"] = "different signed request"
    elif changed == "key":
        key = "different-command-key"
    else:
        actor = "8"
    with pytest.raises(AppException) as caught:
        orders.create_itemized_order(body, idempotency_key=key, actor_id=actor)
    assert caught.value.http_status == (409 if changed == "payload" else 404)
    db = get_sessionmaker()()
    try:
        assert len(db.scalars(select(PlatformOrder).where(PlatformOrder.tenant_id == tid)).all()) == 1
    finally:
        db.close()
