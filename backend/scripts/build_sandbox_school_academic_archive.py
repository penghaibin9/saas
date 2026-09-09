"""分阶段建设标准沙箱学校：阶段 8，历史教务归档闭环。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent)]


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    from app.core.tenant_identity import SANDBOX_SCHOOL, TRIAL_SCHOOL
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import AaArchiveBatch, AaTerm, Tenant
    from app.services.sandbox_school_academic_archive_seed import (
        seed_school_academic_archive_20k,
        validate_school_academic_archive_20k,
    )

    if not db_enabled():
        return 2
    tenant_id = SANDBOX_SCHOOL.tenant_id
    db = get_sessionmaker()()
    try:
        old_tenant = db.get(Tenant, TRIAL_SCHOOL.tenant_id)
        new_tenant = db.get(Tenant, tenant_id)
        if old_tenant is None or old_tenant.tenant_code != TRIAL_SCHOOL.tenant_code:
            return 3
        if new_tenant is None or new_tenant.tenant_code != SANDBOX_SCHOOL.tenant_code:
            return 4
        historical_term = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == tenant_id,
            AaTerm.year_code == "2025-2026",
            AaTerm.term_no == 2,
            AaTerm.is_deleted.is_(False),
        )).one()
        current = int(db.scalar(select(func.count()).select_from(AaArchiveBatch).where(
            AaArchiveBatch.tenant_id == tenant_id,
            AaArchiveBatch.term_id == int(historical_term.id),
            AaArchiveBatch.is_deleted.is_(False),
        )) or 0)
        print(json.dumps({"tenantId": str(tenant_id), "historicalArchiveBatches": current}, ensure_ascii=False))
        if args.dry_run:
            return 0 if current in (0, 1) else 5
        if current == 1:
            print(json.dumps({"resumed": True, "acceptance": validate_school_academic_archive_20k(db, tenant_id)}, ensure_ascii=False, indent=2))
            return 0
        if current != 0:
            return 5
        result = seed_school_academic_archive_20k(db, tenant_id)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
