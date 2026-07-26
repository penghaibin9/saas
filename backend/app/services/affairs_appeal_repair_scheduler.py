"""学工异议/申诉补偿队列的稳定定时触发器。

web scheduler 模式由 ``app.main.lifespan`` 每 5 分钟遍历启用租户并执行补偿；
external scheduler 模式仍通过既有请假逾期、风险超时、辅导员临时代管扫描包装兜底。
节流按租户隔离，禁止同一轮只处理第一个租户。

补偿失败只记录日志，不得覆盖原定时任务结果；原任务失败时仍尝试补偿，然后保留
原异常，避免把真实扫描故障伪装成成功。
"""
from __future__ import annotations

import logging
import threading
import time
from functools import wraps
from typing import Callable

log = logging.getLogger("app.affairs.appeal-repair-scheduler")
_INTERVAL_SECONDS = 5 * 60
_LOCK = threading.Lock()
_LAST_RUN_AT: dict[str, float] = {}
_INSTALLED = False


def _tenant_key() -> str:
    try:
        from app.services.db_service import _tid

        return str(_tid())
    except Exception:  # noqa: BLE001 - 单元测试/启动早期没有租户上下文
        return "__NO_TENANT__"


def run_due(*, force: bool = False) -> dict:
    """按租户节流执行补偿；返回可审计结果，不抛出到原定时任务。"""
    key = _tenant_key()
    now = time.monotonic()
    with _LOCK:
        last = _LAST_RUN_AT.get(key, 0.0)
        if not force and last and now - last < _INTERVAL_SECONDS:
            return {
                "tenantId": key,
                "skipped": True,
                "reason": "interval",
                "claimed": 0,
                "repaired": 0,
                "failed": 0,
            }
        _LAST_RUN_AT[key] = now

    try:
        from app.services.affairs_appeal_repair_service import repair_pending

        result = repair_pending(limit=100)
        return {"tenantId": key, "skipped": False, **(result or {})}
    except Exception as exc:  # noqa: BLE001 - 定时补偿不能反向打断其他扫描
        log.exception("appeal repair scheduled run failed tenant=%s", key)
        return {
            "tenantId": key,
            "skipped": False,
            "claimed": 0,
            "repaired": 0,
            "failed": 1,
            "errorType": type(exc).__name__,
        }


def run_all_tenants() -> dict:
    """web scheduler 单轮：逐租户执行，任一租户失败不影响其他租户。"""
    from sqlalchemy import select

    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        tenant_ids = list(db.scalars(select(Tenant.id).where(Tenant.status == "ACTIVE")))
    finally:
        db.close()

    totals = {"tenants": len(tenant_ids), "claimed": 0, "repaired": 0, "failed": 0, "skipped": 0}
    for tenant_id in tenant_ids:
        try:
            set_tenant({"tenantId": str(tenant_id)})
            result = run_due(force=True)
            totals["claimed"] += int(result.get("claimed") or 0)
            totals["repaired"] += int(result.get("repaired") or 0)
            totals["failed"] += int(result.get("failed") or 0)
            totals["skipped"] += int(bool(result.get("skipped")))
        except Exception:  # noqa: BLE001
            totals["failed"] += 1
            log.exception("appeal repair tenant sweep failed tenant=%s", tenant_id)
        finally:
            set_tenant(None)
    return totals


def _wrap_periodic(original: Callable) -> Callable:
    if getattr(original, "_affairs_appeal_repair_scheduled", False):
        return original

    @wraps(original)
    def wrapped(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        finally:
            run_due()

    wrapped._affairs_appeal_repair_scheduled = True
    wrapped._affairs_appeal_repair_original = original
    return wrapped


def install() -> None:
    """接入既有学工扫描，作为external scheduler与异常场景兜底。"""
    global _INSTALLED
    if _INSTALLED:
        return

    from app.services import affairs_counselor_service, affairs_leave_service, affairs_risk_service

    affairs_leave_service.scan_overdue = _wrap_periodic(affairs_leave_service.scan_overdue)
    affairs_risk_service.scan_timeout = _wrap_periodic(affairs_risk_service.scan_timeout)
    affairs_counselor_service.scan_expired_temps = _wrap_periodic(
        affairs_counselor_service.scan_expired_temps,
    )
    _INSTALLED = True
