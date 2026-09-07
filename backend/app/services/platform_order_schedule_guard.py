"""Canonical service-window guard for commercial PlatformOrder creation.

``platform_service.create_order`` historically reused generic TENANT_META
``status/expireAt`` to schedule every order. That is not commercial evidence: an
active trial, a controlled exception, or stale lifecycle metadata can carry a
future expireAt. Treating it as a paid predecessor makes a NEW/UPGRADE order
start in the future, so mark-paid succeeds but the commercial authority correctly
fails closed with PAID_ORDER_SERVICE_NOT_STARTED.

This wrapper keeps the public command unchanged while making service-window
scheduling depend only on real order facts:
- explicit NEW / UPGRADE start now;
- explicit RENEW continues after the latest paid order for the same tenant + package;
- legacy callers that omit ``orderType`` are inferred as RENEW when a paid
  same-package predecessor exists, preserving the historical "buy again extends
  the current service term" contract;
- otherwise an omitted ``orderType`` is a first NEW purchase and starts now.

``t_order.start_at/end_at`` are MySQL DATETIME columns without fractional-second
precision. MySQL can round a value carrying microseconds to the following second;
an immediate authority read can then observe a newly paid order as briefly
"not started". Normalize service-window writes to the column precision before
persisting them. This keeps fail-closed semantics for genuinely future windows
without requiring an authorization grace period.

The package already uses approved runtime wrappers for legacy services; this
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

        # t_order uses DATETIME(0). Persist exactly at the column precision so
        # MySQL cannot round an immediate NEW/UPGRADE start into the future.
        now = datetime.now().replace(tzinfo=None, microsecond=0)
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

            explicit_order_type = bool(str(body.get("orderType") or "").strip())
            order_type = str(order.order_type or body.get("orderType") or "NEW").strip().upper()

            # Derive the duration from the already validated/persisted order when
            # callers omit durationDays. This preserves package-specific durations
            # instead of silently replacing them with a generic 365-day window.
            if body.get("durationDays") not in (None, ""):
                try:
                    duration_days = int(body.get("durationDays"))
                except (TypeError, ValueError):
                    duration_days = max(1, int((order.end_at - order.start_at).days))
            elif order.end_at is not None and order.start_at is not None:
                duration_days = max(1, int((order.end_at - order.start_at).days))
            else:
                duration_days = 365

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

            # Backward-compatible command semantics: historical callers omitted
            # orderType when buying the same package again and expected the paid
            # term to extend. Infer RENEW from commercial order truth only; never
            # from TENANT_META, which may describe trials/exceptions/stale state.
            if not explicit_order_type and predecessor is not None:
                order_type = "RENEW"
                order.order_type = "RENEW"

            service_start = now
            if order_type == "RENEW" and predecessor_end is not None and predecessor_end > now:
                service_start = predecessor_end.replace(microsecond=0)

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
