"""只读输出 sandbox-school 全域关系闭包报告。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker  # noqa: E402
from app.services.sandbox_school_relationship_closure import (  # noqa: E402
    audit_sandbox_relationship_closure,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="审计 sandbox-school 跨表/跨模块业务关系闭包")
    parser.add_argument("--tenant-id", type=int, default=1000000000000000007)
    parser.add_argument("--fail-on-p0", action="store_true")
    parser.add_argument("--summary", action="store_true", help="只输出汇总、失败项和施工诊断")
    args = parser.parse_args()
    with get_sessionmaker()() as db:
        report = audit_sandbox_relationship_closure(db, args.tenant_id)
    payload = report
    if args.summary:
        payload = {
            "tenantId": report["tenantId"],
            "schema": report["schema"],
            "summary": report["summary"],
            "failures": report["failures"],
            "diagnostics": report["diagnostics"],
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 2 if args.fail_on_p0 and not report["summary"]["p0Passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
