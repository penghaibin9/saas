#!/usr/bin/env python3
"""One-time production-truth materializer.

This utility exists to remove two historical dynamic/hard-coded truths without hand-copying a
90KB seed or 133 ORM table definitions:

1. Patch the public academic-affairs seed to use the canonical sandbox identity and verify the DB
   row before any writes.
2. Materialize the remaining 0001 ORM-owned tables into a frozen MySQL SHOW CREATE TABLE snapshot.

It is NOT used by Alembic at runtime. The resulting frozen files are committed and 0001 consumes
only those static bytes. Re-running against the same verified ORM/MySQL should be idempotent.
"""
from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SEED = BACKEND / "scripts" / "seed_academic_affairs_demo.py"
MIGRATION = BACKEND / "alembic" / "versions" / "0001_init_core_tables.py"
FROZEN_DIR = BACKEND / "alembic" / "frozen"
DDL_FILE = FROZEN_DIR / "0001_baseline_mysql.sql"
TABLE_FILE = FROZEN_DIR / "0001_baseline_tables.txt"
STATEMENT_END = "-- __SCHOOL_LIFECYCLE_STATEMENT_END__"


def patch_seed() -> None:
    text_value = SEED.read_text(encoding="utf-8")
    old = "TID = 1000000000000000004"
    new = "TID = SANDBOX_SCHOOL.tenant_id"

    if old in text_value:
        import_anchor = "from app.core.context import set_tenant  # noqa: E402\n"
        identity_import = "from app.core.tenant_identity import SANDBOX_SCHOOL  # noqa: E402\n"
        if identity_import not in text_value:
            if import_anchor not in text_value:
                raise SystemExit("academic seed import anchor drifted; refusing blind rewrite")
            text_value = text_value.replace(import_anchor, import_anchor + identity_import, 1)
        text_value = text_value.replace(old, new, 1)
    elif new not in text_value:
        raise SystemExit("academic seed TID contract is unknown; refusing blind rewrite")

    main_anchor = '    try:\n        teachers = seed_teachers(db)\n'
    guarded = (
        '    try:\n'
        '        from app.models import Tenant\n'
        '        target = db.get(Tenant, TID)\n'
        '        if target is None or (target.tenant_code or "") != SANDBOX_SCHOOL.tenant_code:\n'
        '            raise RuntimeError(\n'
        '                f"拒绝教务演示种子：tenant_id={TID} 必须对应 "\n'
        '                f"{SANDBOX_SCHOOL.tenant_code!r}，实际={getattr(target, \'tenant_code\', None)!r}"\n'
        '            )\n'
        '        teachers = seed_teachers(db)\n'
    )
    if "拒绝教务演示种子" not in text_value:
        if main_anchor not in text_value:
            raise SystemExit("academic seed main anchor drifted; refusing blind rewrite")
        text_value = text_value.replace(main_anchor, guarded, 1)

    SEED.write_text(text_value, encoding="utf-8")


def load_0001_module():
    spec = importlib.util.spec_from_file_location("freeze_0001_baseline", MIGRATION)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load 0001 migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quote_identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise SystemExit(f"unsafe table name: {name!r}")
    return f"`{name}`"


def materialize_baseline() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if not database_url.startswith("mysql"):
        raise SystemExit("TEST_DATABASE_URL must point at the isolated MySQL 8 materializer database")

    # Importing app.db.base registers the authoritative ORM metadata used by the historical 0001.
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.db.base import metadata  # noqa: PLC0415

    migration = load_0001_module()
    tables = migration._tables_for_baseline(metadata)
    names = [table.name for table in tables]
    if not names:
        raise SystemExit("0001 baseline table set unexpectedly empty")
    if len(names) != len(set(names)):
        raise SystemExit("0001 baseline table set contains duplicates")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            # The database is dedicated to this one-time job. A dirty database would make
            # SHOW CREATE TABLE capture untrustworthy, so fail instead of checkfirst-merging it.
            existing = list(conn.execute(text("SHOW TABLES")))
            if existing:
                raise SystemExit(f"materializer database is not empty: {len(existing)} table(s)")
            metadata.create_all(bind=conn, tables=tables, checkfirst=False)

        statements: list[str] = []
        with engine.connect() as conn:
            for table in tables:
                row = conn.execute(text(f"SHOW CREATE TABLE {quote_identifier(table.name)}")).first()
                if row is None or len(row) < 2:
                    raise SystemExit(f"SHOW CREATE TABLE failed for {table.name}")
                ddl = str(row[1]).strip().rstrip(";")
                if not ddl.upper().startswith("CREATE TABLE"):
                    raise SystemExit(f"unexpected DDL for {table.name}: {ddl[:80]!r}")
                statements.append(ddl)
    finally:
        engine.dispose()

    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    header = (
        "-- Immutable MySQL 8 baseline for Alembic revision 0001_init_core_tables.\n"
        "-- Materialized once from the verified 2026-08-12 ORM using SHOW CREATE TABLE.\n"
        "-- Runtime Alembic MUST NOT import ORM metadata to regenerate or alter these bytes.\n"
        f"-- table_count={len(names)}\n\n"
    )
    body = (f"\n{STATEMENT_END}\n\n").join(statements)
    DDL_FILE.write_text(header + body + f"\n{STATEMENT_END}\n", encoding="utf-8")
    TABLE_FILE.write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"materialized {len(names)} frozen baseline tables")


def main() -> int:
    patch_seed()
    materialize_baseline()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
