"""学工异议/申诉补偿队列的显式定时入口。

``run_due`` 对当前租户执行一次租约任务修复并按租户节流；
``run_all_tenants`` 供独立 scheduler 进程逐租户调用。模块不包装任何其他
定时函数，也不依赖 API router 的导入顺序。
"""
from __future__ import annotations

import logging
import threading
import time

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
    """external scheduler 单轮入口：逐租户执行，任一租户失败不影响其他租户。"""
    from sqlalchemy import select

    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        tenant_ids = list(db.scalars(select(Tenant.id).where(Tenant.status.in_(("ACTIVE", "TRIAL", "active", "trial")))))
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


def install() -> None:
    """兼容空入口；调度已由 Web lifespan / external scheduler 显式调用。"""
    return None
