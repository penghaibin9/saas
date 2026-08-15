"""E-A01 M6 migration contract for rolling-deploy-compatible V3 release fields."""
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


def _upgrade_source() -> str:
    source = M6.read_text(encoding="utf-8")
    return source.split("def upgrade()", 1)[1].split("def downgrade()", 1)[0]


def _downgrade_source() -> str:
    return M6.read_text(encoding="utf-8").split("def downgrade()", 1)[1]


def test_m6_is_linear_after_m5_and_keeps_single_migration_head():
    m5 = _assignments(M5)
    m6 = _assignments(M6)
    assert m6["revision"] == "20260815_internship_e_m6"
    assert m6["down_revision"] == m5["revision"]


def test_m6_expands_release_fields_without_breaking_n_minus_one_and_adds_unlock_evidence():
    source = M6.read_text(encoding="utf-8")
    upgrade = _upgrade_source()
    assert '"released_at"' in source and '"last_released_at"' in source
    assert '"release_reason"' in source and '"last_release_reason"' in source
    assert '"unlock_requested_at"' in source
    assert '"unlock_request_reason"' in source
    assert '"t_internship_volunteer_group"' in source
    assert "new_column_name=" not in upgrade
    assert 'op.drop_column(_TABLE, "last_released_at")' not in upgrade
    assert 'op.drop_column(_TABLE, "last_release_reason")' not in upgrade
    assert "t_student_volunteer" not in source
    assert "t_recruitment_application" not in source


def test_m6_backfills_and_keeps_legacy_and_canonical_release_fields_bidirectionally_compatible():
    source = M6.read_text(encoding="utf-8")
    assert "released_at = COALESCE(released_at, last_released_at)" in source
    assert "last_released_at = COALESCE(last_released_at, released_at)" in source
    assert "release_reason = COALESCE(release_reason, last_release_reason)" in source
    assert "last_release_reason = COALESCE(last_release_reason, release_reason)" in source
    assert "trg_intern_volunteer_release_compat_insert" in source
    assert "trg_intern_volunteer_release_compat_update" in source
    assert "SET NEW.last_released_at = NEW.released_at" in source
    assert "SET NEW.released_at = NEW.last_released_at" in source
    assert "SET NEW.last_release_reason = NEW.release_reason" in source
    assert "SET NEW.release_reason = NEW.last_release_reason" in source


def test_m6_downgrade_copies_canonical_back_to_legacy_before_contracting():
    downgrade = _downgrade_source()
    assert "last_released_at=COALESCE(released_at,last_released_at)" in downgrade
    assert "last_release_reason=COALESCE(release_reason,last_release_reason)" in downgrade
    assert 'op.drop_column(_TABLE, "released_at")' in downgrade
    assert 'op.drop_column(_TABLE, "release_reason")' in downgrade
    assert 'op.drop_column(_TABLE, "last_released_at")' not in downgrade
    assert 'op.drop_column(_TABLE, "last_release_reason")' not in downgrade
