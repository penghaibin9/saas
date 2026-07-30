"""公共文件 ClamAV 扫描 worker：python -m app.workers.file_scan_worker"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import time

from app.services.file_scan_config import get_file_scan_config
from app.services.file_scan_service import process_next_scan_job

log = logging.getLogger("file-scan-worker")


def run(*, once: bool = False, worker_id: str | None = None) -> int:
    config = get_file_scan_config()
    identity = worker_id or os.getenv("FILE_SCAN_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    processed = 0
    while True:
        result = process_next_scan_job(identity)
        if result.get("processed"):
            processed += 1
            log.info("file scan result: %s", result)
        elif once:
            return processed
        else:
            time.sleep(config.poll_seconds)
        if once:
            return processed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="处理至多一个任务后退出")
    parser.add_argument("--worker-id")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(once=args.once, worker_id=args.worker_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
