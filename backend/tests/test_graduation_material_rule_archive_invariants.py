from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RULE_SERVICE = ROOT / "backend/app/modules/graduation/materials/rule_service.py"


def source() -> str:
    return RULE_SERVICE.read_text(encoding="utf-8")


def test_rule_impact_covers_all_material_policy_dimensions():
    text = source()
    required_dimensions = (
        "material_name",
        "biz_stage",
        "owner_role",
        "required",
        "review_required",
        "archive_required",
        "allowed_ext_json",
        "max_files",
        "max_size_bytes",
        "version_policy",
        "sensitivity_level",
        "applicable_major_id",
        "applicable_topic_type",
    )
    impact = text[text.index("def impact_analysis"):text.index("def get_impact")]
    for field in required_dimensions:
        assert f"candidate_items[code].{field} != current_items[code].{field}" in impact


def test_archived_students_and_frozen_materials_are_not_rewritten_by_rule_cutover():
    text = source()
    migration = text[text.index("def _migrate_catalog_to_candidate"):text.index("def activate_rule")]
    assert 'GraduationStudent.stage == "ARCHIVED"' in migration
    assert 'material.archive_status in {"FROZEN", "ARCHIVED"}' in migration
    assert "preserved_archived += 1" in migration
    preserve_guard = migration.index("preserved_archived += 1")
    rule_rewrite = migration.index("material.rule_id = int(candidate.id)")
    assert preserve_guard < rule_rewrite
    assert '"preservedArchived": preserved_archived' in migration


def test_rule_removal_never_discards_a_non_archived_material_with_a_file():
    text = source()
    migration = text[text.index("def _migrate_catalog_to_candidate"):text.index("def activate_rule")]
    assert "if material.current_version_id:" in migration
    assert '"MATERIAL_RULE_REMOVAL_CONFLICT"' in migration
    assert "material.is_deleted = True" in migration
    assert migration.index("if material.current_version_id:") < migration.index("material.is_deleted = True")


def test_rule_activation_reports_preserved_archive_evidence():
    text = source()
    activation = text[text.index("def activate_rule"):]
    assert '"preservedArchived": 0' in activation
    assert '"catalogMigration": {**migration, **initialized}' in activation


def test_rule_activation_requires_expected_version_and_increments_touched_rows():
    text = src("backend/app/modules/graduation/materials/rule_service.py")
    activation = text[text.index("def activate_rule"): ]
    router = src("backend/app/modules/graduation/routers/graduation_material_center.py")
    assert "expected_version: int" in activation
    assert "check_version(int(candidate.version or 0), expected_version)" in activation
    assert "candidate.version = int(candidate.version or 0) + 1" in activation
    assert "row.version = int(row.version or 0) + 1" in activation
    assert "body.expectedVersion" in router
