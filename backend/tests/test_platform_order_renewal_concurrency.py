from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta


def _seed_trial(tenant_id: int) -> None:
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services import platform_service

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, tenant_id)
        if tenant is None:
            db.add(Tenant(
                id=tenant_id,
                tenant_code="renew-concurrency",
                school_name="续费并发回归学校",
                status="ACTIVE",
            ))
        else:
            tenant.status = "ACTIVE"
            tenant.is_deleted = False
        db.commit()
    finally:
        db.close()
    platform_service.put_config_json(tenant_id, "TENANT_META", "-", {
        "status": "trial",
        "packageCode": "trial",
        "environment": "test",
    })


def _pay(created: dict, reason: str) -> dict:
    from app.services import platform_service

    paid = platform_service.order_action(
        created["orderNo"],
        "mark-paid",
        expected_version=int(created["version"]),
        reason=reason,
    )
    if paid.get("repairTaskRequired"):
        paid = platform_service.order_action(
            created["orderNo"],
            "repair-activation",
            expected_version=int(paid["version"]),
            reason=f"{reason}激活修复",
        )
    return paid


def test_two_concurrent_renewal_payments_extend_two_distinct_terms(db_mode):
    """Two paid renewals must buy two periods, not overlap on one predecessor."""
    from app.db.session import get_sessionmaker
    from app.models import PlatformOrder
    from app.services import platform_service

    tenant_id = 1000000000000096265
    _seed_trial(tenant_id)

    first = platform_service.create_order({
        "tenantId": str(tenant_id),
        "packageCode": "professional",
        "orderType": "NEW",
        "durationDays": 30,
        "amount": 1,
        "remark": "并发续费首期",
    })
    assert _pay(first, "并发续费首期支付")["tenantActivated"] is True

    # Both drafts are deliberately created before either renewal is paid. Without
    # payment-time serialization they are both scheduled from the same predecessor.
    renewals = [
        platform_service.create_order({
            "tenantId": str(tenant_id),
            "packageCode": "professional",
            "orderType": "RENEW",
            "durationDays": 30,
            "amount": 1,
            "remark": f"并发续费草稿{idx}",
        })
        for idx in (1, 2)
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_pay, renewal, f"并发续费订单{idx}支付")
            for idx, renewal in enumerate(renewals, start=1)
        ]
        paid = [future.result(timeout=60) for future in futures]
    assert all(item["tenantActivated"] is True for item in paid), paid

    db = get_sessionmaker()()
    try:
        rows = list(db.query(PlatformOrder).filter(
            PlatformOrder.tenant_id == tenant_id,
            PlatformOrder.order_no.in_([first["orderNo"], *(r["orderNo"] for r in renewals)]),
            PlatformOrder.is_deleted.is_(False),
        ).all())
    finally:
        db.close()

    by_no = {row.order_no: row for row in rows}
    first_row = by_no[first["orderNo"]]
    renewal_rows = sorted(
        (by_no[row["orderNo"]] for row in renewals),
        key=lambda row: (row.start_at, row.id),
    )
    assert first_row.end_at is not None
    assert renewal_rows[0].start_at == first_row.end_at
    assert renewal_rows[1].start_at == renewal_rows[0].end_at
    assert renewal_rows[1].end_at - first_row.end_at == timedelta(days=60)

    final_meta = platform_service.tenant_meta(tenant_id)
    assert final_meta["expireAt"] == renewal_rows[1].end_at.isoformat(timespec="seconds")
