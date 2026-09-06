"""预览或执行 sandbox-school 无歧义关系回填。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker  # noqa: E402
from app.services.sandbox_school_relationship_reconcile import (  # noqa: E402
    preview_sandbox_relationship_reconcile,
    reconcile_sandbox_relationships,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="回填 sandbox-school 无歧义业务关系")
    parser.add_argument("--tenant-id", type=int, default=1000000000000000007)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    with get_sessionmaker()() as db:
        report = (
            reconcile_sandbox_relationships(db, args.tenant_id)
            if args.confirm
            else preview_sandbox_relationship_reconcile(db, args.tenant_id)
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
