"""Regression gate: teacher grade writes must not grow a second business implementation."""
from __future__ import annotations

import ast
from pathlib import Path


SERVICES = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "modules"
    / "academic_affairs"
    / "services"
)


def _top_level_defs(path: Path) -> dict[str, int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            counts[node.name] = counts.get(node.name, 0) + 1
    return counts


def test_canonical_grade_service_remains_single_write_rule_owner():
    counts = _top_level_defs(SERVICES / "academic_affairs_grade_service.py")
    assert counts.get("enter_score") == 1
    assert counts.get("submit_task") == 1


def test_grade_transaction_adapter_contains_no_second_grade_state_machine():
    source = (
        SERVICES / "academic_affairs_grade_execution_transaction_guard.py"
    ).read_text(encoding="utf-8")

    assert "return _grade.enter_score(task_id, user, body)" in source
    assert "return _grade.submit_task(task_id, user)" in source
    assert "object_session(task)" in source
    assert "_exec._require_live_teacher(db, task, actor, lock_owner=True)" in source

    # These names belong to the canonical business implementation.  If any returns here, the
    # transaction adapter has started cloning the score/submit state machine again.
    for forbidden in (
        "AaGradeRecord",
        "AaGradeTask",
        "WorkflowInstance",
        "WorkflowTask",
        "freeze_consumer_snapshot",
        "resolve_versioned_roster",
        "ensure_workflow_enabled",
        "_core._audit(",
    ):
        assert forbidden not in source, f"duplicate grade business detail returned: {forbidden}"
