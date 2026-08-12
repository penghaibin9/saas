#!/usr/bin/env python3
"""Migration time-travel gate: historical Alembic DDL must be immutable.

2026-08-12 truth:
- the last runtime ``metadata.create_all`` migration (0001) has been replaced by a frozen MySQL 8
  SHOW CREATE TABLE snapshot for its 133 baseline tables;
- therefore the allowed historical count is now **zero**. There is no create_all/drop_all
  grandfather list to expand;
- current empty-MySQL installability and ORM parity are independently proven by the canonical
  fresh-schema job. Older real-school upgrade rehearsal remains a separate deployment evidence
  concern and must never be inferred from this static checker alone.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "backend" / "alembic" / "versions"
FROZEN_DIR = ROOT / "backend" / "alembic" / "frozen"
BASELINE = VERSIONS / "0001_init_core_tables.py"
DDL = FROZEN_DIR / "0001_baseline_mysql.sql"
TABLES = FROZEN_DIR / "0001_baseline_tables.txt"
STATEMENT_END = "-- __SCHOOL_LIFECYCLE_STATEMENT_END__"
EXPECTED_BASELINE_TABLES = 133
CREATE_TABLE = re.compile(r"(?im)^CREATE TABLE\s+`?[A-Za-z0-9_]+`?\s*\(")


def _dynamic_ddl_migrations() -> list[str]:
    found: list[str] = []
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            raise RuntimeError(f"migration syntax error: {path.name}: {exc}") from exc
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("create_all", "drop_all")
            ):
                found.append(path.name)
                break
    return found


def _check_frozen_0001() -> list[str]:
    errors: list[str] = []
    for path in (BASELINE, DDL, TABLES):
        if not path.is_file():
            errors.append(f"missing frozen 0001 input: {path.relative_to(ROOT)}")
    if errors:
        return errors

    migration = BASELINE.read_text(encoding="utf-8")
    if "app.db.base" in migration or "metadata.create_all" in migration or "metadata.drop_all" in migration:
        errors.append("0001 still imports/regenerates ORM metadata instead of frozen DDL")
    if "0001_baseline_mysql.sql" not in migration or "0001_baseline_tables.txt" not in migration:
        errors.append("0001 does not consume both frozen DDL and table manifest")

    names = [line.strip() for line in TABLES.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if len(names) != EXPECTED_BASELINE_TABLES or len(names) != len(set(names)):
        errors.append(
            f"frozen table manifest drift: expected {EXPECTED_BASELINE_TABLES} unique, "
            f"got {len(names)} / {len(set(names))} unique"
        )

    ddl_text = DDL.read_text(encoding="utf-8")
    statement_count = ddl_text.count(STATEMENT_END)
    create_count = len(CREATE_TABLE.findall(ddl_text))
    if statement_count != EXPECTED_BASELINE_TABLES or create_count != EXPECTED_BASELINE_TABLES:
        errors.append(
            f"frozen DDL drift: statements={statement_count}, CREATE TABLE={create_count}, "
            f"expected={EXPECTED_BASELINE_TABLES}"
        )
    return errors


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not VERSIONS.is_dir():
        print(f"migration_time_travel_error: missing {VERSIONS}", file=sys.stderr)
        return 2

    try:
        dynamic = _dynamic_ddl_migrations()
    except RuntimeError as exc:
        print(f"migration_time_travel_error: {exc}", file=sys.stderr)
        return 2

    errors = _check_frozen_0001()
    if dynamic:
        errors.append("runtime metadata.create_all/drop_all remains in: " + ", ".join(dynamic))

    if errors:
        print("❌ migration time-travel truth is not closed:", file=sys.stderr)
        for error in errors:
            print(f"   - {error}", file=sys.stderr)
        return 1

    print(
        f"✅ migration time-travel debt = 0; 0001 uses {EXPECTED_BASELINE_TABLES} frozen MySQL tables"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
