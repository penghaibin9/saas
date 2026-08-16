"""Operator entrypoint for global Permission Catalog reconciliation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.permission_catalog_reconciliation_service import reconcile_permission_catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="CONTROL_PLANE")
    parser.add_argument("--write", default="")
    args = parser.parse_args()

    result = reconcile_permission_catalog(source=str(args.source or "CONTROL_PLANE"))
    if args.write:
        target = Path(args.write)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
