#!/usr/bin/env python3
# materialize-trigger: 2
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models.base import Base
import app.models  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC = ROOT / "backend" / "alembic"
SQL_PATH = ALEMBIC / "sql" / "0001_internship_standalone_baseline.mysql.sql"
META_PATH = ALEMBIC / "sql" / "0001_internship_standalone_baseline.json"
VERSION_PATH = ALEMBIC / "versions" / "0001_internship_standalone_baseline.py"

FORBIDDEN_PREFIXES = (
    "t_aa_", "t_affairs_", "t_orientation_", "t_graduation_", "t_gd_",
    "t_cs_", "t_campus_", "t_emp_student", "t_emp_job", "t_emp_material", "t_emp_followup",
)

names = sorted(Base.metadata.tables)
bad = [name for name in names if name.startswith(FORBIDDEN_PREFIXES)]
if bad:
    raise SystemExit("forbidden standalone tables: " + ", ".join(bad))

dialect = mysql.dialect()
parts = [
    "-- 跃科岗位实习管理平台 Standalone baseline",
    "-- source: main@adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c",
    "SET NAMES utf8mb4;",
]
for table in Base.metadata.sorted_tables:
    parts.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
    for index in sorted(table.indexes, key=lambda value: value.name or ""):
        parts.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")
sql = "\n\n".join(parts) + "\n"
digest = hashlib.sha256(sql.encode()).hexdigest()

SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
VERSION_PATH.parent.mkdir(parents=True, exist_ok=True)
SQL_PATH.write_text(sql, encoding="utf-8")
META_PATH.write_text(json.dumps({
    "schemaVersion": 1,
    "revision": "0001_internship_standalone_baseline",
    "sourceBaseline": "adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c",
    "tableCount": len(names),
    "tableNames": names,
    "sha256": digest,
    "forbiddenTableCount": 0,
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

version = f'''"""Standalone initial schema frozen from PR #275 W1.

Revision ID: 0001_internship_standalone_baseline
Revises:
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0001_internship_standalone_baseline"
down_revision = None
branch_labels = None
depends_on = None

_TABLES = {tuple(names)!r}
_SQL_SHA256 = "{digest}"


def _sql_text() -> str:
    path = Path(__file__).resolve().parents[1] / "sql" / "0001_internship_standalone_baseline.mysql.sql"
    raw = path.read_text(encoding="utf-8")
    import hashlib
    actual = hashlib.sha256(raw.encode()).hexdigest()
    if actual != _SQL_SHA256:
        raise RuntimeError(f"Standalone baseline SQL digest mismatch: {{actual}}")
    return raw


def upgrade() -> None:
    bind = op.get_bind()
    for statement in _sql_text().split(";\\n\\n"):
        statement = statement.strip()
        if statement:
            bind.exec_driver_sql(statement + ";")


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
    try:
        for table_name in reversed(_TABLES):
            op.drop_table(table_name)
    finally:
        bind.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")
'''
VERSION_PATH.write_text(version, encoding="utf-8")

print(json.dumps({
    "revision": "0001_internship_standalone_baseline",
    "tableCount": len(names),
    "sha256": digest,
    "sql": str(SQL_PATH),
    "version": str(VERSION_PATH),
}, ensure_ascii=False))
