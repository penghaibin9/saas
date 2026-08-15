"""E-A01 M6 migration contract for final V3 volunteer lock/release field names."""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
VERSIONS = HERE / "alembic" / "versions"
M5 = VERSIONS / "20260815_internship_e_m5_decision_placement.py"
M6 = VERSIONS / "20260815_internship_e_m6_volunteer_lock_repair.py"


def _assignments(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return out


def test_m6_is_linear_after_m5_and_keeps_single_migration_head():
    m5 = _assignments(M5)
    m6 = _assignments(M6)
    assert m6["revision"] == "20260815_internship_e_m6"
    assert m6["down_revision"] == m5["revision"]


def test_m6_renames_candidate_release_fields_and_adds_unlock_request_evidence():
    source = M6.read_text(encoding="utf-8")
    assert '"last_released_at"' in source and 'new_column_name="released_at"' in source
    assert '"last_release_reason"' in source and 'new_column_name="release_reason"' in source
    assert '"unlock_requested_at"' in source
    assert '"unlock_request_reason"' in source
    assert '"t_internship_volunteer_group"' in source
    assert "t_student_volunteer" not in source
    assert "t_recruitment_application" not in source


def test_m6_converges_dirty_dual_release_columns_in_both_directions():
    source = M6.read_text(encoding="utf-8")
    assert "COALESCE({canonical}, {legacy})" in source
    assert "op.drop_column(_TABLE, legacy)" in source
    assert '_coalesce_and_drop(canonical="released_at", legacy="last_released_at")' in source
    assert '_coalesce_and_drop(canonical="release_reason", legacy="last_release_reason")' in source
    assert '_coalesce_and_drop(canonical="last_released_at", legacy="released_at")' in source
    assert '_coalesce_and_drop(canonical="last_release_reason", legacy="release_reason")' in source
