#!/usr/bin/env python3
"""P-05 Phase B/C operational gate for CustomRoleSource stable identity.

Default is dry-run. Apply mode is intentionally impossible unless the deployer
explicitly proves the CUSTOM Role write fence is active and reports zero N-1
writers. This script does not pretend an application flag can stop an old pod.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import get_sessionmaker  # noqa: E402
from app.modules.system_admin.services.custom_role_binding_reconciliation_service import (  # noqa: E402
    custom_role_binding_inventory,
    reconcile_custom_role_bindings,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run or reconcile nullable CustomRoleSource.role_id after N-1 writer drain.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply repair. Default is pure-read dry-run.")
    parser.add_argument(
        "--writer-fence-confirmed",
        action="store_true",
        help="Attest the CUSTOM Role create/clone write fence is active and old writer traffic is drained.",
    )
    parser.add_argument(
        "--n-minus-one-writer-count",
        type=int,
        default=None,
        help="Deployment-plane observed N-1 writer count. Apply requires exactly 0.",
    )
    parser.add_argument(
        "--release-sha",
        default=os.getenv("RELEASE_SHA") or os.getenv("GIT_SHA") or "",
        help="Current release SHA written into critical audit. Required for --apply.",
    )
    parser.add_argument(
        "--reason",
        default="P-05 N-1 CustomRoleSource stable binding reconciliation",
        help="Critical audit reason.",
    )
    parser.add_argument(
        "--inventory-only",
        action="store_true",
        help="Print pure-read contract inventory only; ignores --apply.",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    db = get_sessionmaker()()
    try:
        if args.inventory_only:
            report = custom_role_binding_inventory(db)
            db.rollback()
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if report.get("contractReady") else 2

        report = reconcile_custom_role_bindings(
            db,
            dry_run=not args.apply,
            writer_fence_confirmed=bool(args.writer_fence_confirmed),
            n_minus_one_writer_count=args.n_minus_one_writer_count,
            release_sha=str(args.release_sha or ""),
            reason=str(args.reason or ""),
        )
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        if int(report.get("unresolved") or 0) > 0:
            return 2
        return 0
    except Exception as exc:
        db.rollback()
        details = getattr(exc, "details", None)
        payload = {
            "ok": False,
            "errorType": type(exc).__name__,
            "error": str(exc),
            "details": details,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
