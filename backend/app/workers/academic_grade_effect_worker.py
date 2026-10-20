"""External recovery worker: python -m app.workers.academic_grade_effect_worker --tenant-id ID."""
import argparse
import logging
import signal
from threading import Event

from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
from app.db.session import db_enabled
from app.modules.academic_affairs.services.academic_grade_effect_service import run_effect

log = logging.getLogger(__name__)
stop = Event()


def run_once(tenant_id, limit=20):
    if not db_enabled():
        raise RuntimeError('Academic grade effect worker requires DB_ENABLED=true')
    old_tenant, old_user = get_tenant(), get_current_user_ctx()
    try:
        set_tenant(int(tenant_id))
        set_current_user(None)
        processed = 0
        for _ in range(max(1, min(100, int(limit)))):
            if stop.is_set():
                break
            receipt = run_effect()
            if receipt is None:
                break
            processed += 1
            log.info('grade effect job=%s state=%s', receipt['warningScanJobId'], receipt['warningScanState'])
        return processed
    finally:
        set_current_user(old_user)
        set_tenant(old_tenant)


def main():
    parser = argparse.ArgumentParser(description='Recover warning effects without replaying grade commands')
    parser.add_argument('--tenant-id', type=int, required=True)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--interval', type=int, default=30)
    args = parser.parse_args()
    if args.tenant_id <= 0:
        parser.error('--tenant-id must be positive')
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    while not stop.is_set():
        try:
            run_once(args.tenant_id, args.limit)
        except Exception:
            log.exception('Academic grade effect sweep failed tenant=%s', args.tenant_id)
            if args.once:
                return 1
        if args.once:
            return 0
        stop.wait(max(5, args.interval))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
