"""Backdate one browser-created leave only to exercise time-dependent overdue UI flows.

This is a Playwright-only clock fixture. It never creates a leave, workflow task, todo,
cancel record, extension record or audit row, and it never sets OVERDUE/CLOSED itself.
The leave must already be APPROVED through visible browser interactions. The real browser
then clicks the production "scan overdue" / follow-up actions to produce every state change.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

import _mysql_env  # noqa: F401

from app.db.session import get_sessionmaker
from app.models import CsLeave, Tenant

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"


def assert_safe_target() -> None:
    env_name = str(os.getenv("APP_ENV") or "").lower()
    deploy_mode = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env_name in {"prod", "production"} or deploy_mode in {"prod", "production"}:
        raise SystemExit("refusing to backdate student-affairs E2E leave in production")
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")

    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("DATABASE_URL looks like a production or staging database")
    parsed = urlparse(db_url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("student-affairs E2E clock fixture only accepts a local database")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("leave_id", type=int)
    parser.add_argument("--days-back", type=int, default=2)
    args = parser.parse_args()
    if args.days_back < 1 or args.days_back > 30:
        raise SystemExit("--days-back must be between 1 and 30")

    assert_safe_target()
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TENANT_ID)
        if not tenant or tenant.is_deleted or tenant.tenant_code != TENANT_CODE:
            raise SystemExit("sandbox-school tenant mismatch; refusing clock fixture")

        leave = db.get(CsLeave, args.leave_id)
        if (
            not leave
            or leave.is_deleted
            or leave.tenant_id != TENANT_ID
            or leave.affairs_status != "APPROVED"
        ):
            raise SystemExit("target leave must be an APPROVED sandbox-school E2E leave")

        now = datetime.utcnow().replace(second=0, microsecond=0)
        end_at = now - timedelta(days=args.days_back)
        start_at = end_at - timedelta(days=1)
        leave.start_time = start_at
        leave.end_time = end_at
        leave.expected_return_at = end_at
        leave.days = 1.0
        leave.duration = "1.0天"
        leave.overdue_pushed_at = None
        leave.version = int(leave.version or 0) + 1
        db.commit()
        print(json.dumps({
            "leaveId": str(leave.id),
            "status": leave.affairs_status,
            "startTime": start_at.isoformat(timespec="minutes"),
            "endTime": end_at.isoformat(timespec="minutes"),
        }, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
