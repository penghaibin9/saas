"""Single production scheduler process for multi-worker deployments."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.context import set_tenant
from app.db.session import db_enabled, get_sessionmaker
from app.models import Tenant

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app.scheduler")


def _active_tenant_ids() -> list[int]:
    db = get_sessionmaker()()
    try:
        return list(db.scalars(select(Tenant.id).where(Tenant.status == "ACTIVE")))
    finally:
        db.close()


def run_once() -> None:
    from app.modules.internship.services import internship_leave_service
    from app.services import affairs_leave_service
    from app.services import message_campaign_service as camp_svc
    from app.services import message_delivery_service as delivery_svc
    from app.services import message_event_outbox_service as msg_outbox
    from app.services import message_ops_service as ops_svc
    for tenant_id in _active_tenant_ids():
        set_tenant({"tenantId": str(tenant_id)})
        try:
            if settings.INTERNSHIP_OVERDUE_AUTO_SCAN:
                internship_leave_service.refresh_overdue(system=True)
            if settings.AFFAIRS_LEAVE_OVERDUE_AUTO_SCAN:
                affairs_leave_service.scan_overdue()
            # 消息中心：定时发布 + 投递作业 + outbox + 失效/催确认 + 对账
            camp_svc.process_scheduled_campaigns(limit=20)
            delivery_svc.claim_and_process_delivery_jobs(limit=20, worker_id="run_scheduled_jobs")
            msg_outbox.process_pending_outbox(limit=50, worker_id="run_scheduled_jobs")
            camp_svc.process_expired_campaigns(limit=50)
            camp_svc.nudge_unacked_emergency(limit=50)
            ops_svc.reconcile_message_stats()
        except Exception:  # noqa: BLE001
            log.exception("scheduled scan failed tenant=%s", tenant_id)
        finally:
            set_tenant(None)


def cleanup_import_batches() -> None:
    """Clear expired uploaded identity data; safe to run repeatedly."""
    from scripts.cleanup_shared_import_batches import run
    result = run(apply=True, purge_after_days=30)
    log.info("shared import batch cleanup result=%s", result)


def reset_sandbox_if_due(last_reset_date):
    """Run once during the first scheduler minute after China-local midnight."""
    local_now = datetime.utcnow() + timedelta(hours=settings.TIMEZONE_OFFSET_HOURS)
    if not settings.sandbox_auto_reset or local_now.hour != 0:
        return last_reset_date
    if last_reset_date == local_now.date():
        return last_reset_date
    from app.services.sandbox_service import reset_sandbox
    db = get_sessionmaker()()
    try:
        reset_sandbox(db, dry_run=False)
        log.info("sandbox reset complete local_date=%s", local_now.date())
        return local_now.date()
    finally:
        db.close()


def main() -> int:
    if not db_enabled():
        raise RuntimeError("scheduler requires DB_ENABLED=true")
    log.info("external scheduler started")
    next_overdue_at = 0.0
    next_cleanup_at = 0.0
    last_reset_date = (datetime.utcnow() + timedelta(
        hours=settings.TIMEZONE_OFFSET_HOURS)).date()
    while True:
        now = time.monotonic()
        if now >= next_overdue_at:
            run_once()
            next_overdue_at = now + 6 * 60 * 60
        if now >= next_cleanup_at:
            cleanup_import_batches()
            next_cleanup_at = now + 24 * 60 * 60
        last_reset_date = reset_sandbox_if_due(last_reset_date)
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
