"""Standalone scanner lifecycle and health probe: python -m app.file_scan_worker."""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import signal
import tempfile
import threading

from sqlalchemy import func, select

from app.audit_worker import heartbeat_healthy, write_heartbeat
from app.db.session import get_sessionmaker
from app.models.file import FileJob
from app.services.clamav_client import ClamAVClient
from app.services.file_scan_config import get_file_scan_config
from app.services.file_scan_service import process_next_scan_job, reconcile_pending_uploads


def run_once(batch_size):
    recovered = reconcile_pending_uploads(batch_size)
    processed = failed = 0
    for _ in range(batch_size):
        result = process_next_scan_job()
        if not result['processed']:
            break
        processed += 1
        failed += result.get('jobStatus') in ('RETRY', 'DEAD')
    with get_sessionmaker()() as db:
        dead = db.scalar(select(func.count()).select_from(FileJob).where(
            FileJob.job_type == 'FILE_SCAN', FileJob.is_deleted.is_(False), FileJob.status == 'DEAD'))
    config = get_file_scan_config()
    healthy = config.enabled and ClamAVClient(config).ping() and not failed and not dead
    return {'processed': processed, 'failed': failed, 'recovered': recovered,
            'dead': dead, 'healthy': bool(healthy)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--once', action='store_true')
    mode.add_argument('--healthcheck', action='store_true')
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--batch-size', type=int, default=10)
    parser.add_argument('--heartbeat-file', type=Path,
        default=Path(tempfile.gettempdir()) / 'internship-file-scan-heartbeat.json')
    args = parser.parse_args(argv)
    if not 0.2 <= args.interval <= 300 or not 1 <= args.batch_size <= 100:
        parser.error('interval must be 0.2..300; batch-size must be 1..100')
    max_age = max(30, args.batch_size * get_file_scan_config().read_timeout * 3)
    if args.healthcheck:
        return 0 if heartbeat_healthy(args.heartbeat_file, max_age) else 1
    stopping = threading.Event()
    previous = {sig: signal.signal(sig, lambda *_: stopping.set())
                for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        while not stopping.is_set():
            healthy = False
            try:
                outcome = run_once(args.batch_size)
                healthy = outcome['healthy']
                logging.info('Scan jobs processed=%s failed=%s dead=%s',
                             outcome['processed'], outcome['failed'], outcome['dead'])
            except Exception as exc:
                logging.error('File scanning unavailable: %s', type(exc).__name__)
            try:
                write_heartbeat(args.heartbeat_file, healthy)
            except OSError:
                healthy = False
                logging.error('Scan heartbeat unavailable')
            if args.once:
                return 0 if healthy else 1
            stopping.wait(args.interval)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
