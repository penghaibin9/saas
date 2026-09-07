"""Canonical service-window guard for commercial PlatformOrder creation.

``platform_service.create_order`` historically reused generic TENANT_META
``status/expireAt`` to schedule every order. That is not commercial evidence: an
active trial, a controlled exception, or stale lifecycle metadata can carry a
future expireAt. Treating it as a paid predecessor makes a NEW/UPGRADE order
start in the future, so mark-paid succeeds but the commercial authority correctly
fails closed with PAID_ORDER_SERVICE_NOT_STARTED.

This wrapper keeps the public command unchanged while making service-window
scheduling depend only on real order facts:
- NEW / UPGRADE start now;
- RENEW continues after the latest paid order for the same tenant + package;
- RENEW without such a paid predecessor starts now.

The package already uses approved lazy runtime wrappers for legacy services; this
module follows that pattern and is idempotent.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import wraps

from sqlalchemy import select


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None)


def install(platform_service):
    original = platform_service.create_order
    if getattr(original, "_commercial_schedule_guard", False):
        return platform_service

    @wraps(original)
    def create_order(payload: dict):
        body = dict(payload or {})
        result = original(body)

        from app.db.session import get_sessionmaker
        from app.models import PlatformOrder

        order_no = str(result.get("orderNo") or "").strip()
        if not order_no:
            return result

        now = datetime.now().replace(tzinfo=None)
        db = get_sessionmaker()()
        try:
            order = db.scalars(
                select(PlatformOrder)
                .where(
                    PlatformOrder.order_no == order_no,
                    PlatformOrder.is_deleted.is_(False),
                )
                .with_for_update()
            ).first()
            if order is None:
                return result

            order_type = str(order.order_type or body.get("orderType") or "NEW").strip().upper()
            try:
                duration_days = int(body.get("durationDays") or 365)
            except (TypeError, ValueError):
                # The original command has already validated this field. Keep this
                # defensive fallback from creating a second validation contract.
                duration_days = max(1, int((order.end_at - order.start_at).days))

            service_start = now
            if order_type == "RENEW":
                predecessor = db.scalars(
                    select(PlatformOrder)
                    .where(
                        PlatformOrder.tenant_id == int(order.tenant_id),
                        PlatformOrder.package_code == str(order.package_code or ""),
                        PlatformOrder.order_no != order_no,
                        PlatformOrder.status == "paid",
                        PlatformOrder.is_deleted.is_(False),
                        PlatformOrder.end_at.is_not(None),
                    )
                    .order_by(PlatformOrder.end_at.desc(), PlatformOrder.id.desc())
                ).first()
                predecessor_end = _naive(predecessor.end_at) if predecessor is not None else None
                if predecessor_end is not None and predecessor_end > now:
                    service_start = predecessor_end

            order.start_at = service_start
            order.end_at = service_start + timedelta(days=duration_days)
            db.commit()

            out = dict(result)
            out["startAt"] = order.start_at.isoformat(timespec="seconds")
            out["endAt"] = order.end_at.isoformat(timespec="seconds")
            return out
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    create_order._commercial_schedule_guard = True
    platform_service.create_order = create_order
    return platform_service
