"""Migration-backed pytest must preserve Alembic schema truth."""
from pathlib import Path


def test_root_conftest_registers_migrated_schema_guard():
    root = Path(__file__).resolve().parents[1]
    source = (root / "conftest.py").read_text(encoding="utf-8")
    assert 'pytest_plugins = ("pytest_migrated_schema",)' in source


def test_migrated_schema_guard_preserves_schema_and_cleans_rows_only():
    root = Path(__file__).resolve().parents[1]
    source = (root / "pytest_migrated_schema.py").read_text(encoding="utf-8")

    assert 'fixturedef.argname != "db_mode"' in source
    assert 'has_table(_ALEMBIC_TABLE)' in source
    assert 'table_name == _ALEMBIC_TABLE' in source
    assert 'fixture_module._drop_all_mysql = _clear_migrated_schema_data' in source
    assert 'metadata.create_all = _preserve_migrated_schema' in source
    assert 'fixture_module._drop_all_mysql = original_drop' in source
    assert 'delattr(metadata, "create_all")' in source

    # The migration-backed path must never drop schema objects or recreate ORM schema.
    clear_body = source.split("def _clear_migrated_schema_data", 1)[1].split(
        "def _preserve_migrated_schema", 1
    )[0]
    assert "drop_all" not in clear_body
    assert "create_all" not in clear_body
    assert "DELETE FROM" in clear_body
