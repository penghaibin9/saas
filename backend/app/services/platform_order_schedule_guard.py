"""Canonical service-window guard for commercial PlatformOrder commands.

``platform_service.create_order`` historically reused generic TENANT_META
``status/expireAt`` to schedule every order. That is not commercial evidence: an
active trial, a controlled exception, or stale lifecycle metadata can carry a
future expireAt. Treating it as a paid predecessor makes a NEW/UPGRADE order
start in the future, so mark-paid succeeds but the commercial authority correctly
fails closed with PAID_ORDER_SERVICE_NOT_STARTED.

Creation scheduling depends only on real order facts:
- explicit NEW / UPGRADE start now;
- explicit RENEW continues after the latest paid order for the same tenant + package;
- legacy callers that omit ``orderType`` are inferred as RENEW when a paid
  same-package predecessor exists, preserving the historical "buy again extends
  the current service term" contract;
- otherwise an omitted ``orderType`` is a first NEW purchase and starts now.

Renewal payment is also serialized by tenant + package. Two renewal drafts can be
created before either is paid; if both keep the same predecessor window and are
then paid concurrently, both payments would otherwise buy the same service term.
Before each RENEW mark-paid, a MySQL named lock is held across payment + activation
and the order is rebased to the latest paid predecessor. This works across uvicorn
workers and guarantees that two successful payments extend the service chain twice.

``t_order.start_at/end_at`` are MySQL DATETIME columns without fractional-second
precision. Service-window writes are normalized to that column precision so an
immediate authority read cannot observe an order as spuriously future-dated.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps

from sqlalchemy import select, text


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None)


def _duration_days(order) -> int:
    if order.start_at is not None and order.end_at is not None:
        return max(1, int((order.end_at - order.start_at).days))
    return 365


def _latest_paid_predecessor(db, order):
    from app.models import PlatformOrder

    return db.scalars(
        select(PlatformOrder)
        .where(
            PlatformOrder.tenant_id == int(order.tenant_id),
            PlatformOrder.package_code == str(order.package_code or ""),
            PlatformOrder.order_no != str(order.order_no),
            PlatformOrder.status == "paid",
            PlatformOrder.is_deleted.is_(False),
            PlatformOrder.end_at.is_not(None),
        )
        .order_by(PlatformOrder.end_at.desc(), PlatformOrder.id.desc())
    ).first()


@contextmanager
def _serialized_renewal_payment(order_no: str):
    """Hold one cross-worker renewal lane across payment and tenant activation."""
    from app.core.exceptions import AppException
    from app.db.session import get_engine, get_sessionmaker
    from app.models import PlatformOrder

    # Resolve the lane without mutating anything. Canonical order_action remains
    # responsible for missing/order-state validation.
    db = get_sessionmaker()()
    try:
        current = db.scalars(select(PlatformOrder).where(
            PlatformOrder.order_no == str(order_no),
            PlatformOrder.is_deleted.is_(False),
        )).first()
        if current is None or str(current.order_type or "").upper() != "RENEW" \
                or str(current.status or "").lower() != "unpaid":
            yield
            return
        tenant_id = int(current.tenant_id)
        package_code = str(current.package_code or "")
    finally:
        db.close()

    engine = get_engine()
    if engine.dialect.name != "mysql":
        # Production and acceptance use MySQL. Historical experimental dialects
        # keep the canonical command but cannot claim cross-worker serialization.
        yield
        return

    digest = hashlib.sha256(f"{tenant_id}:{package_code}".encode("utf-8")).hexdigest()[:32]
    lock_key = f"platform-renew-{digest}"
    connection = engine.connect()
    acquired = False
    release_failed = False
    try:
        acquired = int(connection.execute(
            text("SELECT GET_LOCK(:lock_key, 15)"), {"lock_key": lock_key}
        ).scalar() or 0) == 1
        if not acquired:
            raise AppException(
                "DATA_CONFLICT",
                "同一学校套餐的续费订单正在处理，请刷新后重试",
                http_status=409,
                details={"tenantId": str(tenant_id), "packageCode": package_code},
            )

        # Rebase only after acquiring the cross-worker lane. The previous renewal
        # may have been paid while this draft was waiting, so its end_at is now the
        # correct predecessor for the current payment.
        db = get_sessionmaker()()
        try:
            order = db.scalars(select(PlatformOrder).where(
                PlatformOrder.order_no == str(order_no),
                PlatformOrder.is_deleted.is_(False),
            )).first()
            if order is not None and str(order.status or "").lower() == "unpaid" \
                    and str(order.order_type or "").upper() == "RENEW":
                now = datetime.now().replace(tzinfo=None, microsecond=0)
                predecessor = _latest_paid_predecessor(db, order)
                predecessor_end = _naive(predecessor.end_at) if predecessor is not None else None
                service_start = max(now, predecessor_end) if predecessor_end is not None else now
                duration_days = _duration_days(order)
                order.start_at = service_start.replace(microsecond=0)
                order.end_at = order.start_at + timedelta(days=duration_days)
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        # The named lock is connection-scoped and survives transaction commits, so
        # keep this dedicated connection open while the canonical command commits
        # payment truth and materializes the tenant lifecycle in its own sessions.
        yield
    finally:
        if acquired:
            try:
                connection.execute(
                    text("SELECT RELEASE_LOCK(:lock_key)"), {"lock_key": lock_key}
                ).scalar()
            except Exception:
                # Never return a pooled connection carrying an unreleased named lock.
                release_failed = True
                connection.invalidate()
        connection.close()
        if release_failed:
            # The business command has already produced its own result; invalidating
            # the lock connection is the safe cleanup and needs no replay.
            pass


def install(platform_service):
    original_create = platform_service.create_order
    original_action = platform_service.order_action
    if getattr(original_create, "_commercial_schedule_guard", False) and \
            getattr(original_action, "_commercial_renewal_payment_guard", False):
        return platform_service

    if not getattr(original_create, "_commercial_schedule_guard", False):
        @wraps(original_create)
        def create_order(payload: dict):
            body = dict(payload or {})
            result = original_create(body)

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

                # Derive duration from the already validated/persisted order when
                # callers omit durationDays; package-specific periods are preserved.
                if body.get("durationDays") not in (None, ""):
                    try:
                        duration_days = int(body.get("durationDays"))
                    except (TypeError, ValueError):
                        duration_days = _duration_days(order)
                else:
                    duration_days = _duration_days(order)

                predecessor = _latest_paid_predecessor(db, order)
                predecessor_end = _naive(predecessor.end_at) if predecessor is not None else None

                # Historical callers omitted orderType for same-package renewal.
                # Infer only from paid commercial order truth, never TENANT_META.
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

    if not getattr(original_action, "_commercial_renewal_payment_guard", False):
        @wraps(original_action)
        def order_action(order_no: str, action: str, **kwargs):
            if str(action or "").strip().lower() != "mark-paid":
                return original_action(order_no, action, **kwargs)
            with _serialized_renewal_payment(str(order_no)):
                return original_action(order_no, action, **kwargs)

        order_action._commercial_renewal_payment_guard = True
        platform_service.order_action = order_action

    return platform_service
