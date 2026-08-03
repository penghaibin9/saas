from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_review_permission_catalog_has_one_authoritative_definition():
    definitions = src("backend/app/modules/graduation/materials/definitions.py")
    command = src("backend/app/modules/graduation/materials/command_service.py")
    query = src("backend/app/modules/graduation/materials/query_service.py")
    assert "REVIEW_PERMISSION_BY_CODE = {" in definitions
    assert "_REVIEW_PERMISSION_BY_CODE = {" not in command
    assert "REVIEW_PERMISSION_BY_CODE.get" in command
    assert "REVIEW_PERMISSION_BY_CODE.get" in query


def test_review_required_custom_codes_fail_rule_validation():
    rule = src("backend/app/modules/graduation/materials/rule_service.py")
    assert "review_required and code not in REVIEW_PERMISSION_BY_CODE" in rule
    assert "未登记受支持的原子审核权限" in rule


def test_archived_students_are_never_initialized_or_repaired_against_new_rule():
    command = src("backend/app/modules/graduation/materials/command_service.py")
    initializer = command[command.index("def initialize_student_materials_in_session"):command.index("def initialize_student_materials(")]
    assert 'student.stage or "").upper() == "ARCHIVED"' in initializer
    assert '"preservedArchived": True' in initializer
    assert initializer.index('"preservedArchived": True') < initializer.index("rule = active_rule")
    assert command.count('func.coalesce(GraduationStudent.stage, "") != "ARCHIVED"') == 2


def test_archived_summary_and_library_use_frozen_rule_not_current_enabled_rule():
    query = src("backend/app/modules/graduation/materials/query_service.py")
    facts = query[query.index("def _facts"):query.index("def _student_aggregate")]
    library = query[query.index("def _rule_for_student"):query.index("def record_versions")]
    assert "archived_rule_id" in facts
    assert "effective_rule_id = case" in facts
    assert "material.rule_id == rule.id" in facts
    assert 'student.stage or "").upper() == "ARCHIVED"' in library
    assert 'archive_status.in_(("FROZEN", "ARCHIVED"))' in library
    assert "len(rule_ids) != 1" in library


def test_review_action_visibility_uses_the_same_exact_material_permission():
    query = src("backend/app/modules/graduation/materials/query_service.py")
    assert "review_permission = REVIEW_PERMISSION_BY_CODE.get" in query
    assert "has_permission(user or {}, review_permission)" in query
    assert '"graduationDesign.proposal.review", "graduationDesign.final.review"' not in query
