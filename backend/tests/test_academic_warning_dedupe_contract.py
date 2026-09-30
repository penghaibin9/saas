"""Regression gate: the warning audit bridge must never clone close_warning again."""
from __future__ import annotations

import ast
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
SERVICES = BACKEND / "app" / "services"


def _top_level_defs(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_academic_service_remains_warning_close_business_owner():
    defs = _top_level_defs(SERVICES / "academic_service.py")
    assert "close_warning" in defs


def test_warning_close_guard_wraps_audit_only():
    source = (SERVICES / "academic_warning_close_audit_guard.py").read_text(encoding="utf-8")

    # The bridge must be attached to the legacy audit sink, not replace the close command.
    assert 'current = getattr(module, "_audit", None)' in source
    assert "module._audit = audit_with_warning_close" in source
    assert "def close_warning(" not in source
    assert '"ACAD_WARNING"' in source
    assert '"CLOSE"' in source

    # These state/transaction details belong only to academic_service.close_warning.
    for forbidden in (
        "warning.status =",
        "warning.close_result =",
        "warning.version +=",
        "module._sync_student_warning",
        "db.commit()",
    ):
        assert forbidden not in source, f"warning close business logic returned to audit guard: {forbidden}"
