"""幂等补齐 007 GD-2027 在办毕设的操作性过程表。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="确认仅向 007 写入幂等在办过程数据")
    args = parser.parse_args()
    from app.core.tenant_identity import SANDBOX_SCHOOL
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import Tenant
    from app.services.sandbox_school_graduation_operational_seed import seed_graduation_operational_coverage
    if not args.confirm:
        print("dry-run: pass --confirm to write 007 only")
        return 0
    if not db_enabled():
        return 2
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, SANDBOX_SCHOOL.tenant_id)
        if tenant is None or tenant.tenant_code != SANDBOX_SCHOOL.tenant_code:
            raise RuntimeError("007 tenant identity mismatch")
        print(json.dumps(seed_graduation_operational_coverage(db, SANDBOX_SCHOOL.tenant_id), ensure_ascii=False, indent=2))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
