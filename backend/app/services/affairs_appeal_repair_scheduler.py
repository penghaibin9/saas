"""学工异议/申诉补偿队列的稳定定时触发器。

复用现有学工定时任务入口，不另起一套进程：请假逾期、风险超时、辅导员临时
代管扫描任一运行时，最多每 5 分钟触发一次申诉补偿。三个任务在 web scheduler
模式下均由 ``app.main.lifespan`` 周期运行；生产 external scheduler 复用同名服务
函数时也会经过本包装。

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
_LAST_RUN_AT = 0.0
_INSTALLED = False


def run_due(*, force: bool = False) -> dict:
    """按进程节流执行补偿；返回可审计结果，不抛出到原定时任务。"""
    global _LAST_RUN_AT
    now = time.monotonic()
    with _LOCK:
        if not force and _LAST_RUN_AT and now - _LAST_RUN_AT < _INTERVAL_SECONDS:
            return {"skipped": True, "reason": "interval", "claimed": 0, "repaired": 0, "failed": 0}
        _LAST_RUN_AT = now

    try:
        from app.services.affairs_appeal_repair_service import repair_pending

        result = repair_pending(limit=100)
        return {"skipped": False, **(result or {})}
    except Exception as exc:  # noqa: BLE001 - 定时补偿不能反向打断其他扫描
        log.exception("appeal repair scheduled run failed")
        return {
            "skipped": False,
            "claimed": 0,
            "repaired": 0,
            "failed": 1,
            "errorType": type(exc).__name__,
        }


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
    """接入现有三条学工周期扫描，形成无人工操作依赖的稳定补偿触发。"""
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
