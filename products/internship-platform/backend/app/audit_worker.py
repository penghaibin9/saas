"""Standalone audit delivery process; supports bounded runs and container health probes."""
from __future__ import annotations
import argparse
import json
import logging
import os
from pathlib import Path
import signal
import tempfile
import threading
import time


def heartbeat_healthy(path: Path, max_age: float = 30) -> bool:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        age = time.time() - float(data['checkedAt'])
        return data['healthy'] is True and 0 <= age <= max_age
    except (OSError, ValueError, TypeError, KeyError):
        return False


def write_heartbeat(path: Path, healthy: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps({'checkedAt': time.time(), 'healthy': healthy,
                                    'pid': os.getpid()}), encoding='utf-8')
    temporary.replace(path)


def run_once(batch_size: int, worker_id: str) -> dict:
    from app.modules.internship.services.internship_audit_service import process_pending, delivery_health
    result = process_pending(limit=batch_size, worker_id=worker_id)
    queue = delivery_health()
    return {**result, 'healthy': not result['failed'] and queue['healthy'],
            'backlog': queue['backlog'], 'dead': queue['dead'], 'stalled': queue['stalled']}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--once', action='store_true')
    mode.add_argument('--healthcheck', action='store_true')
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--heartbeat-file', type=Path,
                        default=Path(tempfile.gettempdir()) / 'internship-audit-heartbeat.json')
    args = parser.parse_args(argv)
    if not 1 <= args.interval <= 300 or not 1 <= args.batch_size <= 1000:
        parser.error('interval must be 1..300 seconds; batch-size must be 1..1000')
    if args.healthcheck:
        return 0 if heartbeat_healthy(args.heartbeat_file, max(30, args.interval * 3)) else 1
    stopping = threading.Event()
    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, lambda *_: stopping.set())
    try:
        while not stopping.is_set():
            healthy = False
            try:
                result = run_once(args.batch_size, f'standalone-audit-{os.getpid()}')
                healthy = bool(result['healthy'])
                write_heartbeat(args.heartbeat_file, healthy)
                print(json.dumps(result), flush=True)
            except Exception as exc:
                # Never print SQL exception messages or bound payloads.
                logging.error('Audit delivery unavailable: %s', type(exc).__name__)
                try:
                    write_heartbeat(args.heartbeat_file, False)
                except OSError:
                    logging.error('Audit heartbeat unavailable')
            if args.once:
                return 0 if healthy else 1
            stopping.wait(args.interval)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
