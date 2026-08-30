"""列出指定租户仍无数据的业务表，供演示数据完整性审计。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="审计租户空表")
    parser.add_argument("--tenant-id", type=int, default=1000000000000000007)
    args = parser.parse_args()

    with get_sessionmaker()() as db:
        schema = db.execute(text("SELECT DATABASE()" )).scalar()
        tables = db.execute(
            text(
                """
                SELECT c.TABLE_NAME, t.TABLE_COMMENT
                  FROM information_schema.COLUMNS c
                  JOIN information_schema.TABLES t
                    ON t.TABLE_SCHEMA=c.TABLE_SCHEMA
                   AND t.TABLE_NAME=c.TABLE_NAME
                 WHERE c.TABLE_SCHEMA=:schema
                   AND c.COLUMN_NAME='tenant_id'
                 ORDER BY c.TABLE_NAME
                """
            ),
            {"schema": schema},
        ).all()
        empty_tables = []
        for table_name, table_comment in tables:
            # 表名来自 information_schema，不接收外部输入。
            row_count = int(
                db.execute(
                    text(f"SELECT COUNT(*) FROM `{table_name}` WHERE tenant_id=:tenant_id"),
                    {"tenant_id": args.tenant_id},
                ).scalar()
                or 0
            )
            if row_count == 0:
                empty_tables.append(
                    {"table": table_name, "comment": table_comment or ""}
                )

    print(
        json.dumps(
            {
                "tenantId": str(args.tenant_id),
                "schema": schema,
                "tenantTableCount": len(tables),
                "emptyTableCount": len(empty_tables),
                "emptyTables": empty_tables,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
