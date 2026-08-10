#!/usr/bin/env python
"""把一个 MySQL 库的结构导成规范化文本，供两条安装路径比对。

配合 check-migration-path-convergence 使用：同一个 HEAD，
「老库一路升级上来」和「全新库一次装到底」必须产出**完全相同**的结构。

规范化处理（只去掉与结构无关的噪音，不放过任何真实差异）：
- 忽略 alembic_version 表内容（版本号本来就一样，表结构才是重点）；
- 忽略 AUTO_INCREMENT 当前值、行数统计等运行时属性；
- 排序表名/列名/索引名，消除导出顺序差异。

用法：
    python scripts/check/dump-mysql-schema.py --url mysql+pymysql://... --out fresh.txt
"""
from __future__ import annotations

import argparse
import sys


def dump(url: str) -> str:
    from sqlalchemy import create_engine, inspect

    engine = create_engine(url)
    insp = inspect(engine)
    lines: list[str] = []
    for table in sorted(insp.get_table_names()):
        if table == "alembic_version":
            continue
        lines.append(f"TABLE {table}")
        for col in sorted(insp.get_columns(table), key=lambda c: c["name"]):
            nullable = "NULL" if col.get("nullable") else "NOT NULL"
            default = col.get("default")
            # server_default 里常见 CURRENT_TIMESTAMP 等，保留原样比对。
            lines.append(
                f"  COLUMN {col['name']} {col['type']!s} {nullable} DEFAULT={default!r}")
        for idx in sorted(insp.get_indexes(table), key=lambda i: (i.get("name") or "")):
            cols = ",".join(idx.get("column_names") or [])
            unique = "UNIQUE" if idx.get("unique") else "INDEX"
            lines.append(f"  {unique} {idx.get('name')} ({cols})")
        pk = insp.get_pk_constraint(table) or {}
        if pk.get("constrained_columns"):
            lines.append(f"  PK ({','.join(pk['constrained_columns'])})")
        for fk in sorted(insp.get_foreign_keys(table),
                         key=lambda f: (f.get("name") or "")):
            lines.append(
                f"  FK {fk.get('name')} ({','.join(fk.get('constrained_columns') or [])})"
                f" -> {fk.get('referred_table')}"
                f"({','.join(fk.get('referred_columns') or [])})")
    engine.dispose()
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(dump(args.url))
    print(f"schema dumped -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
