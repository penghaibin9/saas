"""学工异议/申诉补偿独立调度进程。

生产采用 ``SCHEDULER_MODE=external`` 时运行：

    cd backend && python -m app.affairs_appeal_repair_worker

默认启动即扫描，此后每 5 分钟扫描全部启用租户。进程退出由容器/systemd/Kubernetes
负责拉起；单租户失败不会终止其他租户或整个 worker。
"""
from __future__ import annotations

import argparse
import logging
import signal
import threading
import time

from app.db.session import db_enabled
from app.services.affairs_appeal_repair_scheduler import run_all_tenants

log = logging.getLogger("app.affairs.appeal-repair-worker")
_DEFAULT_INTERVAL_SECONDS = 5 * 60
_STOP = threading.Event()


def run_once() -> dict:
    if not db_enabled():
        raise RuntimeError("学工申诉补偿worker要求 DB_ENABLED=true")
    result = run_all_tenants()
    log.info(
        "appeal repair sweep tenants=%s claimed=%s repaired=%s failed=%s skipped=%s",
        result.get("tenants", 0), result.get("claimed", 0), result.get("repaired", 0),
        result.get("failed", 0), result.get("skipped", 0),
    )
    return result


def run_forever(interval_seconds: int = _DEFAULT_INTERVAL_SECONDS) -> None:
    interval = max(60, int(interval_seconds or _DEFAULT_INTERVAL_SECONDS))
    while not _STOP.is_set():
        started = time.monotonic()
        try:
            run_once()
        except Exception:  # noqa: BLE001 - worker持续运行，故障留日志并进入下一轮
            log.exception("appeal repair sweep failed")
        elapsed = time.monotonic() - started
        _STOP.wait(max(1.0, interval - elapsed))


def _stop(_signum, _frame) -> None:
    _STOP.set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="学工异议/申诉补偿调度进程")
    parser.add_argument("--once", action="store_true", help="只执行一轮后退出")
    parser.add_argument(
        "--interval-seconds", type=int, default=_DEFAULT_INTERVAL_SECONDS,
        help="循环间隔，最小60秒，默认300秒",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    if args.once:
        run_once()
        return 0
    run_forever(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
