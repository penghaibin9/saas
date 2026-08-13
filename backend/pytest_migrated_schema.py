"""Preserve Alembic-built schemas when db_mode runs inside migrated-schema gates.

Normal MySQL test databases still use the repository's existing drop/create fixture.
If the target database already carries ``alembic_version``, the gate is explicitly
validating migration truth, so db_mode may clean rows but must not replace that
schema with ``metadata.create_all()``.
"""
from __future__ import annotations

import inspect
import os
from typing import Final

import pytest


_MIGRATED_DB_CACHE: dict[str, bool] = {}
_ALEMBIC_TABLE: Final[str] = "alembic_version"


def _is_migrated_mysql(test_url: str) -> bool:
    """Return whether this test URL already points at an Alembic-managed schema."""
    normalized = str(test_url or "").strip()
    if not normalized or normalized.startswith("sqlite"):
        return False
    cached = _MIGRATED_DB_CACHE.get(normalized)
    if cached is not None:
        return cached

    from sqlalchemy import create_engine, inspect as sa_inspect

    engine = create_engine(normalized, pool_pre_ping=True, future=True)
    try:
        with engine.connect() as conn:
            migrated = bool(sa_inspect(conn).has_table(_ALEMBIC_TABLE))
    finally:
        engine.dispose()
    _MIGRATED_DB_CACHE[normalized] = migrated
    return migrated


def _quoted_table(name: str) -> str:
    return "`" + str(name).replace("`", "``") + "`"


def _clear_migrated_schema_data(engine, _metadata) -> None:
    """Clear test rows while preserving every migrated table/index/trigger."""
    from sqlalchemy import inspect as sa_inspect, text
    from sqlalchemy.exc import OperationalError

    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        try:
            # Include migration-only tables too; keep Alembic's version marker intact.
            table_names = list(sa_inspect(conn).get_table_names())
            for table_name in reversed(table_names):
                if table_name == _ALEMBIC_TABLE:
                    continue
                quoted = _quoted_table(table_name)
                try:
                    conn.execute(text(f"DELETE FROM {quoted}"))
                except OperationalError as exc:
                    # Production immutability triggers intentionally reject row DELETE
                    # with SIGNAL 1644. TRUNCATE is test-infrastructure DDL and does not
                    # weaken the application/runtime immutability contract.
                    if "1644" not in str(getattr(exc, "orig", exc)):
                        raise
                    conn.execute(text(f"TRUNCATE TABLE {quoted}"))
        finally:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


def _preserve_migrated_schema(*_args, **_kwargs) -> None:
    """Intentional no-op replacing metadata.create_all only during db_mode setup."""
    return None


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_fixture_setup(fixturedef, request):
    """Make the existing db_mode fixture migration-safe without duplicating its seed logic."""
    if fixturedef.argname != "db_mode":
        yield
        return

    test_url = os.environ.get("TEST_DATABASE_URL", "")
    if not _is_migrated_mysql(test_url):
        yield
        return

    fixture_module = inspect.getmodule(fixturedef.func)
    if fixture_module is None or not hasattr(fixture_module, "_drop_all_mysql"):
        raise RuntimeError(
            "migrated-schema db_mode guard could not locate the canonical _drop_all_mysql helper"
        )

    from app.db.base import metadata

    original_drop = fixture_module._drop_all_mysql
    had_create_override = "create_all" in metadata.__dict__
    original_create_override = metadata.__dict__.get("create_all")
    fixture_module._drop_all_mysql = _clear_migrated_schema_data
    metadata.create_all = _preserve_migrated_schema
    try:
        yield
    finally:
        fixture_module._drop_all_mysql = original_drop
        if had_create_override:
            metadata.create_all = original_create_override
        else:
            delattr(metadata, "create_all")
