"""幂等写入 007 标准演示学校的组织治理、审批和控制面事实。"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="确认只写入 sandbox-school(007)")
    args = ap.parse_args()
    if not args.confirm:
        print("refuse: pass --confirm to write only 007")
        return 2
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services.sandbox_service import SANDBOX_CODE, SANDBOX_TID
    from app.services.sandbox_school_governance_seed import seed_governance_coverage
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, SANDBOX_TID)
        if tenant is None or tenant.tenant_code != SANDBOX_CODE:
            raise RuntimeError("target tenant identity check failed")
        print(json.dumps(seed_governance_coverage(db, SANDBOX_TID), ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
