"""Verify the three PLAT-C ORM tables against a migrated database.

This is an operational Gold gate.  It is intentionally separate from pytest so
the normal unit suite never silently skips a missing MySQL acceptance database.
"""
from __future__ import annotations

import argparse
from collections.abc import Iterable

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Inspector
from sqlalchemy.sql.sqltypes import NullType

from app.models import DocumentCompareResult, FileDerivedArtifact, StudentLifecycleFact


TABLES = (
    FileDerivedArtifact.__table__,
    DocumentCompareResult.__table__,
    StudentLifecycleFact.__table__,
)


def _column_names(items: Iterable[dict]) -> tuple[str, ...]:
    return tuple(item["name"] for item in items)


def _index_map(items: Iterable[dict]) -> dict[str, tuple[tuple[str, ...], bool]]:
    return {
        str(item["name"]): (tuple(item["column_names"]), bool(item.get("unique")))
        for item in items
    }


def _unique_map(items: Iterable[dict]) -> dict[str, tuple[str, ...]]:
    return {
        str(item["name"]): tuple(item["column_names"])
        for item in items
        if item.get("name")
    }


def _verify_table(inspector: Inspector, table) -> list[str]:
    failures: list[str] = []
    name = table.name
    reflected_columns = inspector.get_columns(name)
    reflected_by_name = {item["name"]: item for item in reflected_columns}
    orm_names = tuple(column.name for column in table.columns)
    reflected_names = _column_names(reflected_columns)
    if set(orm_names) != set(reflected_names):
        failures.append(f"{name}: columns ORM={orm_names} DB={reflected_names}")

    for column in table.columns:
        reflected = reflected_by_name.get(column.name)
        if reflected is None:
            continue
        if bool(column.nullable) != bool(reflected["nullable"]):
            failures.append(
                f"{name}.{column.name}: nullable ORM={column.nullable} DB={reflected['nullable']}"
            )
        orm_affinity = column.type._type_affinity
        db_affinity = reflected["type"]._type_affinity
        if orm_affinity is NullType or db_affinity is NullType or orm_affinity is not db_affinity:
            failures.append(
                f"{name}.{column.name}: type ORM={column.type!s} DB={reflected['type']!s}"
            )
        orm_length = getattr(column.type, "length", None)
        db_length = getattr(reflected["type"], "length", None)
        if orm_length != db_length:
            failures.append(
                f"{name}.{column.name}: length ORM={orm_length} DB={db_length}"
            )

    orm_pk = tuple(column.name for column in table.primary_key.columns)
    db_pk = tuple(inspector.get_pk_constraint(name).get("constrained_columns") or ())
    if orm_pk != db_pk:
        failures.append(f"{name}: primary key ORM={orm_pk} DB={db_pk}")

    orm_indexes = {
        index.name: (tuple(column.name for column in index.columns), bool(index.unique))
        for index in table.indexes
    }
    db_indexes = _index_map(inspector.get_indexes(name))
    if orm_indexes != db_indexes:
        failures.append(f"{name}: indexes ORM={orm_indexes} DB={db_indexes}")

    orm_uniques = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint" and constraint.name
    }
    db_uniques = _unique_map(inspector.get_unique_constraints(name))
    if orm_uniques != db_uniques:
        failures.append(f"{name}: unique constraints ORM={orm_uniques} DB={db_uniques}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify PLAT-C Fresh MySQL ORM/schema parity")
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()

    engine = create_engine(args.database_url, pool_pre_ping=True)
    try:
        inspector = inspect(engine)
        failures = [failure for table in TABLES for failure in _verify_table(inspector, table)]
    finally:
        engine.dispose()

    if failures:
        print("C_SCHEMA_PARITY=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("C_SCHEMA_PARITY=PASS")
    for table in TABLES:
        print(f"PARITY_TABLE={table.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
