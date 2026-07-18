"""Audit ORM/database tenant isolation and tenant-leading indexes.

This is read-only.  It reports global tables, tenant tables without a leading
tenant index, and unique constraints that may accidentally be global.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import UniqueConstraint, inspect

from app.db.base import metadata
from app.db.session import get_engine

GLOBAL_TABLES = {
    "t_tenant", "t_permission", "t_auth_refresh_token", "t_auth_blocked_jti",
}
GLOBAL_UNIQUES = {
    ("t_tenant", ("tenant_code",)),
    ("t_permission", ("permission_code",)),
    ("t_user", ("wx_openid",)),
    # 平台订单由超级管理员跨租户按 order_no 定位，编号属于平台级标识。
    ("t_order", ("order_no",)),
    ("t_auth_refresh_token", ("token_hash",)),
    ("t_auth_blocked_jti", ("jti",)),
}


def _args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero for missing tenant columns/indexes")
    return parser.parse_args()


def main() -> int:
    args = _args()
    failures: list[str] = []
    warnings: list[str] = []
    for table in sorted(metadata.tables.values(), key=lambda item: item.name):
        columns = set(table.c.keys())
        if table.name in GLOBAL_TABLES:
            continue
        if "tenant_id" not in columns:
            failures.append(f"{table.name}: missing tenant_id")
            continue
        leading = any(tuple(index.columns.keys())[:1] == ("tenant_id",)
                      for index in table.indexes)
        unique_leading = any(tuple(constraint.columns.keys())[:1] == ("tenant_id",)
                             for constraint in table.constraints
                             if isinstance(constraint, UniqueConstraint))
        if not (leading or unique_leading):
            failures.append(f"{table.name}: no tenant-leading index")
        for constraint in table.constraints:
            if not isinstance(constraint, UniqueConstraint):
                continue
            cols = tuple(constraint.columns.keys())
            if cols and cols[0] != "tenant_id" and (table.name, cols) not in GLOBAL_UNIQUES:
                warnings.append(f"{table.name}: review global unique {cols}")

    # Compare the live database so migrations missing from an environment are visible.
    inspector = inspect(get_engine())
    live_tables = set(inspector.get_table_names())
    for table in sorted(metadata.tables):
        if table not in live_tables:
            warnings.append(f"{table}: ORM table missing in database")

    print(f"tables={len(metadata.tables)} failures={len(failures)} warnings={len(warnings)}")
    for item in failures:
        print("FAIL", item)
    for item in warnings:
        print("WARN", item)
    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
