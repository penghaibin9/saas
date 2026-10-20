"""分阶段建设标准沙箱学校：阶段 6，2027 届就业准备与帮扶。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent)]


def _count(db, model, tenant_id: int) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(
        model.tenant_id == tenant_id,
        model.is_deleted.is_(False),
    )) or 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    from app.core.tenant_identity import SANDBOX_SCHOOL, TRIAL_SCHOOL
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import EmpCompany, EmpJob, EmpStudent, Tenant
    from app.services.sandbox_school_employment_seed import (
        seed_school_employment_20k,
        validate_employment_facts_20k,
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

        current = {
            "students": _count(db, EmpStudent, tenant_id),
            "jobs": _count(db, EmpJob, tenant_id),
            "companies": _count(db, EmpCompany, tenant_id),
        }
        print(json.dumps({"tenantId": str(tenant_id), "current": current}, ensure_ascii=False))
        empty_state = {"students": 0, "jobs": 0, "companies": 80}
        completed_state = {"students": 6400, "jobs": 160, "companies": 80}
        if args.dry_run:
            return 0 if current in (empty_state, completed_state) else 5
        if current == completed_state:
            acceptance = validate_employment_facts_20k(db, tenant_id)
            print(json.dumps({"resumed": True, "acceptance": acceptance}, ensure_ascii=False, indent=2))
            return 0
        if current != empty_state:
            return 5

        result = seed_school_employment_20k(db, tenant_id)
        acceptance = validate_employment_facts_20k(db, tenant_id)
        print(json.dumps({"result": result, "acceptance": acceptance}, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
