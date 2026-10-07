from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import get_sessionmaker  # noqa: E402
from app.services.sandbox_school_academic_flow_gap_seed import seed_academic_flow_gap_coverage  # noqa: E402


def main() -> int:
    db = get_sessionmaker()()
    try:
        report = seed_academic_flow_gap_coverage(db, 1000000000000000007)
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
