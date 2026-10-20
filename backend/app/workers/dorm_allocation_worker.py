"""Run `python -m app.workers.dorm_allocation_worker` beside the API service."""
import argparse
import logging
import threading

from app.db.session import db_enabled
from app.services.dorm_allocation_publish_job import run_one

log = logging.getLogger("app.dorm.allocation-worker")


def main():
    parser = argparse.ArgumentParser(description="处理持久化住宿发布任务")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not db_enabled():
        raise RuntimeError("住宿发布 worker 需要真实 MySQL")
    logging.basicConfig(level=logging.INFO)
    stop = threading.Event()
    import signal
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    while not stop.is_set():
        try:
            result = run_one()
            if result.get("processed"):
                log.info("dorm publication job=%s status=%s", result["jobId"], result["status"])
        except Exception as error:
            # Transaction rollback leaves RUNNING recoverable. Do not log SQL,
            # raw parameters or credentials in user-visible task diagnostics.
            log.error("dorm publication interrupted (%s); retained for retry", type(error).__name__)
            if args.once:
                raise
            stop.wait(5)
            continue
        if args.once:
            return
        if not result.get("processed"):
            stop.wait(2)


if __name__ == "__main__":
    main()
