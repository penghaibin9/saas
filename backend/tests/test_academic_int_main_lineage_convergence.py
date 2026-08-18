"""Source contracts for final Academic A/main × sealed INT Alembic convergence."""
from __future__ import annotations

from pathlib import Path


VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _read(name: str) -> str:
    return (VERSIONS / name).read_text(encoding="utf-8")


def test_final_lineage_merge_has_exact_a_and_int_parents_and_no_ddl():
    source = _read("20260818_academic_main_int_merge.py")
    compact = "".join(source.split())

    assert 'revision="20260818_acad_main_int_merge"' in compact
    assert 'down_revision=("20260817_aa_prog_expand","20260818_acad_int_task_pc_prov",)' in compact
    assert "def upgrade()" in source and "pass" in source
    assert "def downgrade()" in source and source.count("pass") == 2
    assert "op." not in source
    assert "UPDATE " not in source.upper()


def test_a_nullable_expand_is_branch_order_safe_without_owning_int_constraints():
    source = _read("20260817_aa_prog_expand.py")
    upper = source.upper()

    assert 'down_revision = "20260816_merge_ctrl_intern_e"' in source
    assert 'if "series_key" not in _columns("t_aa_program")' in source
    assert 'if "formation_mode" not in _columns("t_aa_program_course")' in source
    assert "create_unique_constraint" not in source
    assert "alter_column" not in source
    assert "UPDATE T_AA_PROGRAM" not in upper
    assert "UPDATE T_AA_PROGRAM_COURSE" not in upper
    assert "LEGACY-" not in source


def test_int_shared_schema_is_branch_order_safe_and_keeps_final_authority():
    ac4 = _read("20260816_academic_int_ac4_schema.py")
    series = _read("20260817_academic_int_program_series.py")

    assert '_ensure_formation_column("t_aa_program_course")' in ac4
    assert "op.alter_column(" in ac4
    assert "ck_aa_program_course_formation_mode" in ac4
    assert "ck_aa_teaching_task_formation_mode" in ac4
    assert "uk_aa_task_batch_editable_scope" in ac4

    assert 'if "series_key" not in _columns("t_aa_program")' in series
    assert 'if "uk_aa_program_series_version" not in _unique_names("t_aa_program")' in series
    assert "UPDATE T_AA_PROGRAM" not in series.upper()
    assert "LEGACY-" not in series
