"""CLI for the mandatory pre-migration PLAT-C order lock."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.platform.document_lifecycle.order_lock import (
    COrderLockStopped,
    verify_c_order_lock,
)


def main() -> int:
    backend_root = BACKEND_ROOT
    repository_root = backend_root.parent
    parser = argparse.ArgumentParser(description="Verify PLAT-C C7 migration order lock")
    parser.add_argument(
        "--integration-head",
        default=os.getenv("PLAT_B_INTEGRATION_HEAD", ""),
        help="exact PLAT_B_INTEGRATION_HEAD emitted by the B integration session",
    )
    parser.add_argument(
        "--alembic-head",
        default=os.getenv("PLAT_B_ALEMBIC_HEAD", ""),
        help="exact PLAT_B_ALEMBIC_HEAD emitted by the B integration session",
    )
    args = parser.parse_args()
    try:
        evidence = verify_c_order_lock(
            repository_root=repository_root,
            backend_root=backend_root,
            integration_head=args.integration_head,
            expected_alembic_head=args.alembic_head,
        )
    except COrderLockStopped as exc:
        print(f"C_ORDER_LOCK=STOP reason={exc}", file=sys.stderr)
        return 2
    print("C_ORDER_LOCK=PASS")
    print(f"PLAT_B_INTEGRATION_HEAD={evidence.integration_head}")
    print(f"CURRENT_C_HEAD={evidence.current_head}")
    print(f"PLAT_B_ALEMBIC_HEAD={evidence.alembic_head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
