"""Single production scheduler process for multi-worker deployments."""
from __future__ import annotations

import logging
import time

from sqlalchemy import select

from app.core.config import settings
from app.core.context import set_tenant
from app.db.session import db_enabled, get_sessionmaker
from app.models import Tenant

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app.scheduler")


def _active_tenant_ids() -> list[int]:
    db = get_sessionmaker()()
    try:
        return list(db.scalars(select(Tenant.id).where(Tenant.status == "ACTIVE")))
    finally:
        db.close()


def run_once() -> None:
    from app.modules.internship.services import internship_leave_service
    from app.services import affairs_leave_service
    for tenant_id in _active_tenant_ids():
        set_tenant({"tenantId": str(tenant_id)})
        try:
            if settings.INTERNSHIP_OVERDUE_AUTO_SCAN:
                internship_leave_service.refresh_overdue(system=True)
            if settings.AFFAIRS_LEAVE_OVERDUE_AUTO_SCAN:
                affairs_leave_service.scan_overdue()
        except Exception:  # noqa: BLE001
            log.exception("scheduled scan failed tenant=%s", tenant_id)
        finally:
            set_tenant(None)


def main() -> int:
    if not db_enabled():
        raise RuntimeError("scheduler requires DB_ENABLED=true")
    log.info("external scheduler started")
    while True:
        started = time.monotonic()
        run_once()
        elapsed = time.monotonic() - started
        time.sleep(max(60, 6 * 60 * 60 - elapsed))


if __name__ == "__main__":
    raise SystemExit(main())
