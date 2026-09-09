"""输出 AA-001～024 演示流程覆盖审计。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker  # noqa: E402
from app.services.sandbox_school_academic_flow_coverage import audit_academic_flow_coverage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=int, default=1000000000000000007)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--fail-on-gap", action="store_true")
    args = parser.parse_args()
    with get_sessionmaker()() as db:
        report = audit_academic_flow_coverage(db, args.tenant_id)
    payload = report if args.all else {
        "tenantId": report["tenantId"],
        "summary": report["summary"],
        "failures": report["failures"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 2 if args.fail_on_gap and report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
