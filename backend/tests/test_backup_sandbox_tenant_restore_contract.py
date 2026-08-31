from __future__ import annotations

import importlib.util
from io import StringIO
from pathlib import Path

from sqlalchemy.dialects.mysql import dialect as mysql_dialect


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_sandbox_tenant.py"


def _module():
    spec = importlib.util.spec_from_file_location("backup_sandbox_tenant_contract", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Engine:
    dialect = mysql_dialect()


def test_restore_wrapper_suspends_and_recreates_compound_triggers_exactly():
    module = _module()
    trigger = {
        "TRIGGER_NAME": "trg_exact_lock",
        "ACTION_TIMING": "AFTER",
        "EVENT_MANIPULATION": "INSERT",
        "EVENT_OBJECT_TABLE": "t_exact_fact",
        "ACTION_STATEMENT": "BEGIN INSERT INTO t_lock(fact_id) VALUES (NEW.id); END",
    }

    preamble = StringIO()
    module._write_trigger_preamble(preamble, _Engine(), [trigger])
    assert "DROP TRIGGER IF EXISTS trg_exact_lock;" in preamble.getvalue()

    epilogue = StringIO()
    module._write_trigger_epilogue(epilogue, _Engine(), [trigger])
    rendered = epilogue.getvalue()
    assert "DELIMITER $$" in rendered
    assert (
        "CREATE TRIGGER trg_exact_lock AFTER INSERT ON t_exact_fact FOR EACH ROW "
        "BEGIN INSERT INTO t_lock(fact_id) VALUES (NEW.id); END$$"
    ) in rendered
    assert rendered.endswith("DELIMITER ;\n")


def test_fallback_dump_is_utf8mb4_and_never_assigns_generated_columns():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'stream.write("SET NAMES utf8mb4;\\n")' in source
    assert 'stream.write(b"SET NAMES utf8mb4;\\n")' in source
    assert 'if not column.get("computed")' in source
    assert "_write_trigger_preamble(stream, engine, triggers)" in source
    assert "_write_trigger_epilogue(stream, engine, triggers)" in source


def test_unicode_sql_literal_round_trips_without_lossy_encoding():
    module = _module()
    assert module._literal("定稿 / 学业预警") == "'定稿 / 学业预警'"
