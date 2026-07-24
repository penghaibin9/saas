"""独立调度进程：按任务类别拆频率，任务级异常隔离，输出可观测指标。"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from sqlalchemy import func, select

from app.core.config import settings
from app.core.context import set_tenant
from app.core.timeutil import local_now, utc_now_naive
from app.db.session import db_enabled, get_sessionmaker
from app.models import Tenant

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app.scheduler")

# 频率（秒）
INTERVAL_DELIVERY = 15          # 消息投递 / Outbox
INTERVAL_SCHEDULED_MSG = 45     # 定时消息到点发布
INTERVAL_EXPIRE_NUDGE = 120     # 失效 + 紧急确认催办
INTERVAL_LEAVE_OVERDUE = 30 * 60
INTERVAL_STATS = 15 * 60
INTERVAL_CLEANUP = 24 * 60 * 60
INTERVAL_INTEGRITY = 24 * 60 * 60


@dataclass
class JobMetric:
    name: str
    last_success_at: float | None = None
    last_error_at: float | None = None
    last_error: str | None = None
    run_count: int = 0
    error_count: int = 0
    pending_job_count: int = 0
    dead_job_count: int = 0
    oldest_pending_age: float | None = None

    def lag_seconds(self) -> float | None:
        if self.last_success_at is None:
            return None
        return max(0.0, time.time() - self.last_success_at)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "scheduler_last_success_at": (
                datetime.utcfromtimestamp(self.last_success_at).isoformat() + "Z"
                if self.last_success_at else None),
            "scheduler_lag_seconds": self.lag_seconds(),
            "pending_job_count": self.pending_job_count,
            "dead_job_count": self.dead_job_count,
            "oldest_pending_age": self.oldest_pending_age,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
        }


_METRICS: dict[str, JobMetric] = {}


def get_scheduler_metrics() -> list[dict]:
    return [m.as_dict() for m in _METRICS.values()]


def _metric(name: str) -> JobMetric:
    if name not in _METRICS:
        _METRICS[name] = JobMetric(name=name)
    return _METRICS[name]


def _schedulable_tenant_ids() -> list[int]:
    """ACTIVE + TRIAL 均需调度（试用校同样有消息/请假时效）。"""
    db = get_sessionmaker()()
    try:
        return list(db.scalars(select(Tenant.id).where(
            Tenant.status.in_(("ACTIVE", "TRIAL", "active", "trial")))))
    finally:
        db.close()


def _run_isolated(name: str, fn: Callable[[], object]) -> None:
    m = _metric(name)
    try:
        fn()
        m.last_success_at = time.time()
        m.run_count += 1
        m.last_error = None
    except Exception as e:  # noqa: BLE001
        m.error_count += 1
        m.last_error_at = time.time()
        m.last_error = f"{type(e).__name__}: {e}"
        log.exception("scheduler job failed name=%s", name)


def _refresh_delivery_metrics() -> None:
    from app.models import MessageDeliveryJob
    m = _metric("delivery")
    db = get_sessionmaker()()
    try:
        now = utc_now_naive()
        pending = db.scalar(select(func.count()).select_from(MessageDeliveryJob).where(
            MessageDeliveryJob.is_deleted.is_(False),
            MessageDeliveryJob.status.in_(("PENDING", "RETRY_WAIT", "PROCESSING")),
        )) or 0
        dead = db.scalar(select(func.count()).select_from(MessageDeliveryJob).where(
            MessageDeliveryJob.is_deleted.is_(False),
            MessageDeliveryJob.status == "DEAD",
        )) or 0
        oldest = db.scalar(select(func.min(MessageDeliveryJob.created_at)).where(
            MessageDeliveryJob.is_deleted.is_(False),
            MessageDeliveryJob.status.in_(("PENDING", "RETRY_WAIT")),
        ))
        m.pending_job_count = int(pending)
        m.dead_job_count = int(dead)
        if oldest is not None:
            age = (now - oldest).total_seconds() if hasattr(oldest, "timestamp") else None
            m.oldest_pending_age = float(age) if age is not None else None
    except Exception:  # noqa: BLE001
        log.exception("refresh delivery metrics failed")
    finally:
        db.close()


def job_delivery_and_outbox() -> None:
    from app.services import message_delivery_service as delivery_svc
    from app.services import message_event_outbox_service as msg_outbox
    from app.services import message_campaign_service as camp_svc

    for tenant_id in _schedulable_tenant_ids():
        set_tenant({"tenantId": str(tenant_id)})
        try:
            _run_isolated(
                f"delivery:{tenant_id}",
                lambda: delivery_svc.claim_and_process_delivery_jobs(
                    limit=40, worker_id="scheduler-delivery"))
            _run_isolated(
                f"outbox:{tenant_id}",
                lambda: msg_outbox.process_pending_outbox(
                    limit=80, worker_id="scheduler-outbox"))
            _run_isolated(
                f"repair_publishing:{tenant_id}",
                lambda: camp_svc.repair_publishing_without_jobs(limit=20))
        finally:
            set_tenant(None)
    _refresh_delivery_metrics()


def job_scheduled_messages() -> None:
    from app.services import message_campaign_service as camp_svc
    for tenant_id in _schedulable_tenant_ids():
        set_tenant({"tenantId": str(tenant_id)})
        try:
            _run_isolated(
                f"scheduled_msg:{tenant_id}",
                lambda: camp_svc.process_scheduled_campaigns(limit=30))
        finally:
            set_tenant(None)


def job_expire_and_nudge() -> None:
    from app.services import message_campaign_service as camp_svc
    for tenant_id in _schedulable_tenant_ids():
        set_tenant({"tenantId": str(tenant_id)})
        try:
            _run_isolated(
                f"expire:{tenant_id}",
                lambda: camp_svc.process_expired_campaigns(limit=80))
            _run_isolated(
                f"nudge:{tenant_id}",
                lambda: camp_svc.nudge_unacked_emergency(limit=80))
        finally:
            set_tenant(None)


def job_leave_overdue() -> None:
    from app.modules.internship.services import internship_leave_service
    from app.services import affairs_leave_service
    for tenant_id in _schedulable_tenant_ids():
        set_tenant({"tenantId": str(tenant_id)})
        try:
            if settings.INTERNSHIP_OVERDUE_AUTO_SCAN:
                _run_isolated(
                    f"internship_overdue:{tenant_id}",
                    lambda: internship_leave_service.refresh_overdue(system=True))
            if settings.AFFAIRS_LEAVE_OVERDUE_AUTO_SCAN:
                _run_isolated(
                    f"affairs_overdue:{tenant_id}",
                    lambda: affairs_leave_service.scan_overdue())
        finally:
            set_tenant(None)


def job_stats_reconcile() -> None:
    from app.services import message_ops_service as ops_svc
    for tenant_id in _schedulable_tenant_ids():
        set_tenant({"tenantId": str(tenant_id)})
        try:
            _run_isolated(
                f"stats:{tenant_id}",
                lambda: ops_svc.reconcile_message_stats())
        finally:
            set_tenant(None)


def cleanup_import_batches() -> None:
    from scripts.cleanup_shared_import_batches import run
    result = run(apply=True, purge_after_days=30)
    log.info("shared import batch cleanup result=%s", result)


def reset_sandbox_if_due(last_reset_date):
    """中国本地午夜后第一轮调度触发沙箱重置。"""
    local = local_now()
    if not settings.sandbox_auto_reset or local.hour != 0:
        return last_reset_date
    if last_reset_date == local.date():
        return last_reset_date
    from app.services.sandbox_service import reset_sandbox
    db = get_sessionmaker()()
    try:
        reset_sandbox(db, dry_run=False)
        log.info("sandbox reset complete local_date=%s", local.date())
        return local.date()
    finally:
        db.close()


@dataclass
class _Ticker:
    interval: float
    next_at: float = 0.0
    fn: Callable[[], None] = field(repr=False, default=lambda: None)

    def maybe_run(self, now: float) -> None:
        if now < self.next_at:
            return
        self.fn()
        self.next_at = now + self.interval


def main() -> int:
    if not db_enabled():
        raise RuntimeError("scheduler requires DB_ENABLED=true")
    log.info(
        "external scheduler started intervals delivery=%ss scheduled=%ss expire=%ss leave=%ss stats=%ss",
        INTERVAL_DELIVERY, INTERVAL_SCHEDULED_MSG, INTERVAL_EXPIRE_NUDGE,
        INTERVAL_LEAVE_OVERDUE, INTERVAL_STATS)
    now0 = time.monotonic()
    tickers = [
        _Ticker(INTERVAL_DELIVERY, now0, job_delivery_and_outbox),
        _Ticker(INTERVAL_SCHEDULED_MSG, now0, job_scheduled_messages),
        _Ticker(INTERVAL_EXPIRE_NUDGE, now0, job_expire_and_nudge),
        _Ticker(INTERVAL_LEAVE_OVERDUE, now0, job_leave_overdue),
        _Ticker(INTERVAL_STATS, now0, job_stats_reconcile),
        _Ticker(INTERVAL_CLEANUP, now0, lambda: _run_isolated("cleanup", cleanup_import_batches)),
    ]
    last_reset_date = local_now().date()
    while True:
        now = time.monotonic()
        for t in tickers:
            try:
                t.maybe_run(now)
            except Exception:  # noqa: BLE001 — ticker 自身保护
                log.exception("ticker crashed interval=%s", t.interval)
        last_reset_date = reset_sandbox_if_due(last_reset_date)
        if int(now) % 60 < 2:
            log.info("scheduler_metrics %s", get_scheduler_metrics()[:8])
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
