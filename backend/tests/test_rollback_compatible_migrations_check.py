from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts/check/check-rollback-compatible-migrations.py"
SPEC = importlib.util.spec_from_file_location("rollback_compatible_migrations_check", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def _migration(tmp_path: Path, upgrade_body: str) -> Path:
    path = tmp_path / "migration.py"
    path.write_text(
        "from alembic import op\n\n"
        "def upgrade():\n"
        f"{upgrade_body}\n",
        encoding="utf-8",
    )
    return path


def test_same_name_trigger_replacement_is_not_a_schema_contraction(tmp_path):
    path = _migration(
        tmp_path,
        "    op.execute(\"DROP TRIGGER IF EXISTS stable_guard\")\n"
        "    op.execute(f\"\"\"CREATE TRIGGER stable_guard BEFORE DELETE ON sample "
        "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='guard-{1}'\"\"\")",
    )
    assert CHECKER.violations(path) == []


def test_unmatched_trigger_drop_remains_blocked(tmp_path):
    path = _migration(tmp_path, "    op.execute(\"DROP TRIGGER IF EXISTS retired_guard\")")
    errors = CHECKER.violations(path)
    assert len(errors) == 1
    assert "destructive raw SQL" in errors[0]


def test_table_drop_remains_blocked_even_when_a_trigger_is_created(tmp_path):
    path = _migration(
        tmp_path,
        "    op.execute(\"DROP TABLE old_contract\")\n"
        "    op.execute(\"CREATE TRIGGER old_contract BEFORE DELETE ON sample "
        "FOR EACH ROW SIGNAL SQLSTATE '45000'\")",
    )
    errors = CHECKER.violations(path)
    assert len(errors) == 1
    assert "DROP TABLE" in errors[0]
