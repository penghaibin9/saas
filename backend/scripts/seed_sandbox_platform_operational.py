from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        print("refuse: pass --confirm")
        return 2
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services.sandbox_service import SANDBOX_CODE, SANDBOX_TID
    from app.services.sandbox_school_platform_operational_seed import seed_platform_operational_coverage

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, SANDBOX_TID)
        if not tenant or tenant.tenant_code != SANDBOX_CODE:
            raise RuntimeError("target tenant identity check failed")
        result = seed_platform_operational_coverage(db, SANDBOX_TID)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
