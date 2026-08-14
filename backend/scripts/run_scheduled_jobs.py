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
from app.core.timeutil import utc_now_naive
from app.db.session import db_enabled, get_sessionmaker
from app.models import Tenant

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app.scheduler")

# 频率（秒）
INTERVAL_DELIVERY = 15          # 消息投递 / Outbox
INTERVAL_STUDENT_AFFAIRS = 60    # 学工补偿租约 + 异步导出 + 审批导出
INTERVAL_ACADEMIC_EFFECTIVE = 60 # Stage C1：已批准的未来生效学籍异动
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
    tenant_skip_count: int = 0

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
            "tenant_skip_count": self.tenant_skip_count,
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


def _candidate_tenant_ids() -> list[int]:
    """Enumerate candidates only; effective-state policy decides execution."""
    db = get_sessionmaker()()
    try:
        return list(db.scalars(
            select(Tenant.id)
            .where(Tenant.is_deleted.is_(False))
            .order_by(Tenant.id.asc())
        ))
    finally:
        db.close()


def _record_tenant_skip(name: str, tenant_id: int, job_class: str, *,
                        effective_status: str = "unresolved",
                        reason: str = "TENANT_STATE_UNRESOLVED") -> None:
    _metric(name).tenant_skip_count += 1
    log.warning(
        "scheduler_tenant_skipped tenantId=%s jobClass=%s effectiveStatus=%s reason=%s",
        tenant_id, job_class, effective_status, reason,
    )


def _run_for_tenants(name: str, job_class: str, fn: Callable[[int], object]) -> None:
    """Resolve canonical state for every job/tenant iteration and fail closed."""
    from app.services import tenant_effective_state_service as tenant_state

    allowed_key = {
        tenant_state.BACKGROUND_BUSINESS_WRITE: "businessWriteAllowed",
        tenant_state.BACKGROUND_MAINTENANCE: "maintenanceAllowed",
        tenant_state.BACKGROUND_AUTH_SECURITY: "authSecurityAllowed",
    }.get(job_class)
    if allowed_key is None:
        raise ValueError(f"unknown background job class: {job_class}")

    for tenant_id in _candidate_tenant_ids():
        try:
            policy = tenant_state.background_execution_policy(tenant_id)
        except Exception as exc:  # noqa: BLE001
            _record_tenant_skip(
                name, tenant_id, job_class,
                reason=getattr(exc, "code", None) or type(exc).__name__,
            )
            continue
        if not bool(policy.get(allowed_key)):
            _record_tenant_skip(
                name, tenant_id, job_class,
                effective_status=str(policy.get("effectiveStatus") or "unresolved"),
                reason=str(policy.get("reason") or "TENANT_STATE_UNRESOLVED"),
            )
            continue
        set_tenant({"tenantId": str(tenant_id)})
        try:
            _run_isolated(f"{name}:{tenant_id}", lambda tid=tenant_id: fn(tid))
        finally:
            set_tenant(None)


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
    from app.services import password_reset_service as password_reset_svc
    from app.services import message_channel_delivery_service as channel_svc
    from app.services import tenant_effective_state_service as tenant_state
    from app.modules.internship.services import internship_audit_service as internship_audit

    _run_for_tenants(
        "delivery", tenant_state.BACKGROUND_BUSINESS_WRITE,
        lambda _tid: delivery_svc.claim_and_process_delivery_jobs(
            limit=40, worker_id="scheduler-delivery"),
    )
    _run_for_tenants(
        "outbox", tenant_state.BACKGROUND_BUSINESS_WRITE,
        lambda _tid: msg_outbox.process_pending_outbox(
            limit=80, worker_id="scheduler-outbox"),
    )
    _run_for_tenants(
        "channel_delivery", tenant_state.BACKGROUND_BUSINESS_WRITE,
        lambda _tid: channel_svc.claim_and_process_channel_deliveries(
            limit=100, worker_id="scheduler-channel"),
    )
    _run_for_tenants(
        "repair_publishing", tenant_state.BACKGROUND_BUSINESS_WRITE,
        lambda _tid: camp_svc.repair_publishing_without_jobs(limit=20),
    )
    _run_for_tenants(
        "password_reset_sms", tenant_state.BACKGROUND_AUTH_SECURITY,
        lambda tenant_id: password_reset_svc.process_delivery_jobs(
            limit=30, worker_id="scheduler-password-reset", tenant_id=tenant_id),
    )
    _run_isolated(
        "internship_audit_outbox",
        lambda: internship_audit.process_pending(
            limit=80, worker_id="scheduler-audit-outbox"),
    )
    _refresh_delivery_metrics()


def job_scheduled_messages() -> None:
    from app.services import message_campaign_service as camp_svc
    from app.services import tenant_effective_state_service as tenant_state
    _run_for_tenants(
        "scheduled_msg", tenant_state.BACKGROUND_BUSINESS_WRITE,
        lambda _tid: camp_svc.process_scheduled_campaigns(limit=30),
    )


def job_expire_and_nudge() -> None:
    from app.services import message_campaign_service as camp_svc
    from app.services import tenant_effective_state_service as tenant_state
    _run_for_tenants(
        "expire", tenant_state.BACKGROUND_BUSINESS_WRITE,
        lambda _tid: camp_svc.process_expired_campaigns(limit=80),
    )
    _run_for_tenants(
        "nudge", tenant_state.BACKGROUND_BUSINESS_WRITE,
        lambda _tid: camp_svc.nudge_unacked_emergency(limit=80),
    )


def job_student_affairs_background() -> None:
    """Student-affairs mutation jobs require a writable effective tenant."""
    from app.services import affairs_appeal_repair_service as repair
    from app.services import affairs_archive_service as archive
    from app.services import affairs_leave_export_service as leave_export
    from app.services import approval_export_service as approval_export
    from app.services import tenant_effective_state_service as tenant_state

    _run_for_tenants("affairs_appeal_repair", tenant_state.BACKGROUND_BUSINESS_WRITE,
                     lambda _tid: repair.repair_pending(limit=100))
    _run_for_tenants("affairs_leave_export", tenant_state.BACKGROUND_BUSINESS_WRITE,
                     lambda tenant_id: leave_export.run_pending(
                         limit=2, worker_id=f"scheduler-affairs:{tenant_id}"))
    _run_for_tenants("approval_export", tenant_state.BACKGROUND_BUSINESS_WRITE,
                     lambda tenant_id: approval_export.run_pending(
                         limit=2, worker_id=f"scheduler-approval:{tenant_id}"))
    _run_for_tenants("affairs_archive_package", tenant_state.BACKGROUND_BUSINESS_WRITE,
                     lambda _tid: archive.run_pending_packages(limit=2))


def job_academic_future_effective() -> None:
    """Stage C1 due changes create business facts and require writable effective state."""
    from app.modules.academic_affairs.services import academic_affairs_change_temporal_guard as temporal
    from app.services import tenant_effective_state_service as tenant_state
    _run_for_tenants(
        "academic_future_effective", tenant_state.BACKGROUND_BUSINESS_WRITE,
        lambda _tid: temporal.apply_due_changes(limit=100),
    )


def job_leave_overdue() -> None:
    from app.modules.internship.services import internship_leave_service
    from app.services import affairs_leave_service
    from app.services import tenant_effective_state_service as tenant_state
    if settings.INTERNSHIP_OVERDUE_AUTO_SCAN:
        _run_for_tenants("internship_overdue", tenant_state.BACKGROUND_BUSINESS_WRITE,
                         lambda _tid: internship_leave_service.refresh_overdue(system=True))
    if settings.AFFAIRS_LEAVE_OVERDUE_AUTO_SCAN:
        _run_for_tenants("affairs_overdue", tenant_state.BACKGROUND_BUSINESS_WRITE,
                         lambda _tid: affairs_leave_service.scan_overdue())


def job_risk_timeout() -> None:
    """Risk timeout processing mutates business state."""
    if not settings.AFFAIRS_RISK_TIMEOUT_AUTO_SCAN:
        return
    from app.services import affairs_risk_service
    from app.services import tenant_effective_state_service as tenant_state
    _run_for_tenants("affairs_risk_timeout", tenant_state.BACKGROUND_BUSINESS_WRITE,
                     lambda _tid: affairs_risk_service.scan_timeout())


def job_counselor_temp_expire() -> None:
    """Ending temporary counselor assignments mutates business facts."""
    if not settings.AFFAIRS_COUNSELOR_TEMP_AUTO_SCAN:
        return
    from app.services import affairs_counselor_service
    from app.services import tenant_effective_state_service as tenant_state
    _run_for_tenants("affairs_counselor_temp", tenant_state.BACKGROUND_BUSINESS_WRITE,
                     lambda _tid: affairs_counselor_service.scan_expired_temps())


def job_stats_reconcile() -> None:
    """Derived counter repair is maintenance and remains enabled for readonly/expired tenants."""
    from app.services import message_ops_service as ops_svc
    from app.services import tenant_effective_state_service as tenant_state
    _run_for_tenants("stats", tenant_state.BACKGROUND_MAINTENANCE,
                     lambda _tid: ops_svc.reconcile_message_stats())


def cleanup_import_batches() -> None:
    from scripts.cleanup_shared_import_batches import run
    result = run(apply=True, purge_after_days=30)
    log.info("shared import batch cleanup result=%s", result)


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
        "external scheduler started intervals delivery=%ss affairs=%ss academic_effective=%ss scheduled=%ss expire=%ss leave=%ss risk=%ss stats=%ss",
        INTERVAL_DELIVERY, INTERVAL_STUDENT_AFFAIRS, INTERVAL_ACADEMIC_EFFECTIVE,
        INTERVAL_SCHEDULED_MSG, INTERVAL_EXPIRE_NUDGE,
        INTERVAL_LEAVE_OVERDUE, INTERVAL_LEAVE_OVERDUE, INTERVAL_STATS)
    now0 = time.monotonic()
    tickers = [
        _Ticker(INTERVAL_DELIVERY, now0, job_delivery_and_outbox),
        _Ticker(INTERVAL_STUDENT_AFFAIRS, now0, job_student_affairs_background),
        _Ticker(INTERVAL_ACADEMIC_EFFECTIVE, now0, job_academic_future_effective),
        _Ticker(INTERVAL_SCHEDULED_MSG, now0, job_scheduled_messages),
        _Ticker(INTERVAL_EXPIRE_NUDGE, now0, job_expire_and_nudge),
        _Ticker(INTERVAL_LEAVE_OVERDUE, now0, job_leave_overdue),
        _Ticker(INTERVAL_LEAVE_OVERDUE, now0, job_risk_timeout),
        _Ticker(INTERVAL_LEAVE_OVERDUE, now0, job_counselor_temp_expire),
        _Ticker(INTERVAL_STATS, now0, job_stats_reconcile),
        _Ticker(INTERVAL_CLEANUP, now0, lambda: _run_isolated("cleanup", cleanup_import_batches)),
    ]
    while True:
        now = time.monotonic()
        for t in tickers:
            try:
                t.maybe_run(now)
            except Exception:  # noqa: BLE001 — ticker 自身保护
                log.exception("ticker crashed interval=%s", t.interval)
        if int(now) % 60 < 2:
            log.info("scheduler_metrics %s", get_scheduler_metrics()[:8])
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
