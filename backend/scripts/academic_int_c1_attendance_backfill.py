"""Operator command for C-C1 legacy Attendance source governance.

Dry-run is the default. Pass --apply only after reviewing the inventory/reconciliation output.
This command only backfills source_type=ADMIN_SPECIAL when a same-tenant historical audit
proves source=ADMIN_MANUAL. It never invents reason/evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Keep direct ``python scripts/...py`` execution consistent with the repository's production
# maintenance-script convention: the backend root must be importable before importing ``app``.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services.academic_affairs_attendance_migration_inventory import (
    backfill_proven_legacy_admin_sources,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sample-limit", type=int, default=50)
    parser.add_argument("--operator", default="ACADEMIC_INT_C1")
    args = parser.parse_args()

    db = get_sessionmaker()()
    try:
        report = backfill_proven_legacy_admin_sources(
            db,
            args.tenant_id,
            apply=bool(args.apply),
            sample_limit=args.sample_limit,
            operator=args.operator,
        )
        if args.apply:
            db.commit()
            report["commitPerformed"] = True
        else:
            db.rollback()
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
