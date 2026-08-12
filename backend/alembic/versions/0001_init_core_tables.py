"""init core tables — immutable MySQL baseline.

Revision ID: 0001_init_core_tables
Revises:
Create Date: 2026-07-04

2026-08-12 production-truth closeout
─────────────────────────────────────
The historical implementation imported the *current* ORM and called ``metadata.create_all`` for
133 tables that had no later explicit create-table migration. That made revision 0001 time-travel:
replaying the same revision on different dates could produce different schemas.

The remaining baseline was materialized once on MySQL 8 from the exact verified ORM into:

- ``alembic/frozen/0001_baseline_mysql.sql`` — SHOW CREATE TABLE bytes, ordered by metadata
  dependency order;
- ``alembic/frozen/0001_baseline_tables.txt`` — the same 133 table names for reverse-order
  downgrade.

Runtime migration never imports application ORM metadata and never regenerates these files.
Changing the current models therefore cannot silently change historical revision 0001.
"""
from __future__ import annotations

import re
from pathlib import Path

from alembic import op

revision = "0001_init_core_tables"
down_revision = None
branch_labels = None
depends_on = None

_FROZEN_DIR = Path(__file__).resolve().parents[1] / "frozen"
_DDL_FILE = _FROZEN_DIR / "0001_baseline_mysql.sql"
_TABLE_FILE = _FROZEN_DIR / "0001_baseline_tables.txt"
_STATEMENT_END = "-- __SCHOOL_LIFECYCLE_STATEMENT_END__"
_EXPECTED_TABLE_COUNT = 133
_SAFE_TABLE = re.compile(r"^[A-Za-z0-9_]+$")


def _table_names() -> list[str]:
    if not _TABLE_FILE.is_file():
        raise RuntimeError(f"frozen 0001 table manifest missing: {_TABLE_FILE}")
    names = [line.strip() for line in _TABLE_FILE.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if len(names) != _EXPECTED_TABLE_COUNT or len(names) != len(set(names)):
        raise RuntimeError(
            f"frozen 0001 table manifest drift: expected {_EXPECTED_TABLE_COUNT} unique tables, "
            f"got {len(names)} / {len(set(names))} unique"
        )
    unsafe = [name for name in names if not _SAFE_TABLE.fullmatch(name)]
    if unsafe:
        raise RuntimeError(f"unsafe table name(s) in frozen 0001 manifest: {unsafe!r}")
    return names


def _ddl_statements() -> list[str]:
    if not _DDL_FILE.is_file():
        raise RuntimeError(f"frozen 0001 DDL missing: {_DDL_FILE}")
    raw = _DDL_FILE.read_text(encoding="utf-8")
    statements: list[str] = []
    for chunk in raw.split(_STATEMENT_END):
        # Header comments are evidence only; do not send them together with CREATE TABLE to the
        # MySQL driver because multi-statement/comment handling varies by driver settings.
        lines = [line for line in chunk.splitlines() if not line.lstrip().startswith("--")]
        statement = "\n".join(lines).strip().rstrip(";").strip()
        if not statement:
            continue
        if not statement.upper().startswith("CREATE TABLE"):
            raise RuntimeError(f"unexpected statement in frozen 0001 DDL: {statement[:120]!r}")
        statements.append(statement)
    if len(statements) != _EXPECTED_TABLE_COUNT:
        raise RuntimeError(
            f"frozen 0001 DDL drift: expected {_EXPECTED_TABLE_COUNT} CREATE TABLE statements, "
            f"got {len(statements)}"
        )
    return statements


def upgrade() -> None:
    # PyMySQL treats percent signs as interpolation tokens whenever SQLAlchemy passes an empty
    # parameter tuple. SHOW CREATE TABLE output can legitimately contain '%' (for example date
    # formats), so execute the immutable DDL through the same DBAPI connection with *no* args.
    bind = op.get_bind()
    cursor = bind.connection.cursor()
    try:
        for statement in _ddl_statements():
            cursor.execute(statement)
    finally:
        cursor.close()


def downgrade() -> None:
    # Reverse dependency order captured by the one-time metadata.sorted_tables materializer.
    for table_name in reversed(_table_names()):
        op.drop_table(table_name)
