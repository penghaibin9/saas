"""Preserve Alembic-built schemas only for explicit migrated-schema pytest gates.

Normal MySQL test databases keep the repository's existing drop/create fixture even if a
local database happens to contain an ``alembic_version`` table. The preservation path is
reserved for the dedicated migrated-schema database (``student_lifecycle_migrated``) or
an explicit ``PYTEST_PRESERVE_MIGRATED_SCHEMA=1`` override, and still requires a real
Alembic version table before it may replace db_mode's schema-reset helpers.
"""
from __future__ import annotations

import inspect
import os
from typing import Final

import pytest


_MIGRATED_DB_CACHE: dict[str, bool] = {}
_ALEMBIC_TABLE: Final[str] = "alembic_version"
_MIGRATED_SCHEMA_ENV: Final[str] = "PYTEST_PRESERVE_MIGRATED_SCHEMA"
_KNOWN_MIGRATED_DB: Final[str] = "student_lifecycle_migrated"
_TRUTHY: Final[set[str]] = {"1", "true", "yes", "on"}


def _migrated_schema_requested(test_url: str) -> bool:
    """Return whether this pytest process explicitly targets migration-built schema truth.

    An explicit environment value wins, including false values. Without an override we only
    auto-enable the repository's dedicated CI migrated-schema database. This prevents a
    developer's ordinary test database from changing fixture semantics merely because it was
    previously created by Alembic.
    """
    raw_flag = os.environ.get(_MIGRATED_SCHEMA_ENV)
    if raw_flag is not None:
        return str(raw_flag).strip().lower() in _TRUTHY

    normalized = str(test_url or "").strip()
    if not normalized or normalized.startswith("sqlite"):
        return False
    try:
        from sqlalchemy.engine import make_url

        database = str(make_url(normalized).database or "").strip()
    except Exception:
        return False
    return database == _KNOWN_MIGRATED_DB


def _is_migrated_mysql(test_url: str) -> bool:
    """Return whether the requested gate points at a real Alembic-managed MySQL schema."""
    normalized = str(test_url or "").strip()
    if not _migrated_schema_requested(normalized):
        return False
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
