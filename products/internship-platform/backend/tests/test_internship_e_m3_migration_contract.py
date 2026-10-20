"""E-A01 M3 migration contract: profile + immutable application material evidence."""
from __future__ import annotations

from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "alembic" / "versions" / "20260815_internship_e_m3_material_snapshot.py"


def test_m3_is_linear_after_e1_and_adds_only_e55_authority():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "20260815_internship_e_m3"' in source
    assert 'down_revision = "20260815_internship_e_m1"' in source
    for table in (
        "t_internship_student_profile",
        "t_internship_student_profile_item",
        "t_internship_application_material_snapshot",
    ):
        assert f'"{table}"' in source
    assert '"application_statement"' in source
    assert '"material_snapshot_id"' in source
    assert '"application_material_policy_json"' in source
    for forbidden in (
        "t_student_volunteer", "t_recruitment_application", "t_enterprise_job", "t_placement_result",
    ):
        assert forbidden not in source


def test_m3_does_not_backfill_current_profile_into_historical_applications():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "UPDATE t_internship_application" not in source
    assert "INSERT INTO t_internship_application_material_snapshot" not in source
    assert "nullable=True" in source


def test_snapshot_table_is_mysql_immutable_at_database_boundary():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "trg_intern_material_snapshot_no_update" in source
    assert "trg_intern_material_snapshot_no_delete" in source
    assert "BEFORE UPDATE ON t_internship_application_material_snapshot" in source
    assert "BEFORE DELETE ON t_internship_application_material_snapshot" in source
    assert "INTERNSHIP_MATERIAL_SNAPSHOT_IMMUTABLE" in source
    assert "SIGNAL SQLSTATE '45000'" in source
