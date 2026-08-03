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


def test_archived_library_reads_frozen_rule_in_real_mysql(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import GraduationBatch, GraduationStudent
    from app.models.graduation_material import (
        GraduationMaterialItem, GraduationMaterialRule, GraduationStudentMaterial,
    )
    from app.modules.graduation.materials.query_service import student_library

    tenant_id = 1000000000000000001
    user = {
        "userId": "1", "realName": "归档规则测试管理员", "userType": "ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN", "tenantId": str(tenant_id),
        "permissions": ["*"], "dataScope": "ALL",
    }
    set_tenant({"tenantId": str(tenant_id), "tenantCode": "demo"})
    set_current_user(user)
    db = get_sessionmaker()()
    try:
        batch = GraduationBatch(
            tenant_id=tenant_id, batch_name="冻结规则行为测试", batch_no="FROZEN-RULE-BEHAVIOR",
            planned_count=1, status="RUNNING", archive_status="NOT_ARCHIVED",
        )
        db.add(batch); db.flush()
        frozen_rule = GraduationMaterialRule(
            tenant_id=tenant_id, batch_id=batch.id, rule_code="GD_MATERIAL_STANDARD",
            rule_name="历史冻结规则", rule_version=1, status="DISABLED", enabled=False,
            default_owner_role="STUDENT", version_policy="IMMUTABLE_APPEND",
            archive_required=True, sensitivity_level="SENSITIVE", max_files=1, max_size_bytes=1024,
        )
        active_rule = GraduationMaterialRule(
            tenant_id=tenant_id, batch_id=batch.id, rule_code="GD_MATERIAL_STANDARD",
            rule_name="当前新规则", rule_version=2, status="ENABLED", enabled=True,
            default_owner_role="STUDENT", version_policy="IMMUTABLE_APPEND",
            archive_required=True, sensitivity_level="SENSITIVE", max_files=1, max_size_bytes=1024,
        )
        db.add_all([frozen_rule, active_rule]); db.flush()
        db.add_all([
            GraduationMaterialItem(
                tenant_id=tenant_id, rule_id=frozen_rule.id, biz_stage="FINAL_APPROVED",
                material_code="THESIS_FINAL", material_name="历史论文定稿名称", owner_role="STUDENT",
                required=True, allowed_ext_json=["pdf"], max_files=1, max_size_bytes=1024,
                version_policy="IMMUTABLE_APPEND", review_required=True, archive_required=True,
                sensitivity_level="SENSITIVE", sort_no=1, enabled=True,
            ),
            GraduationMaterialItem(
                tenant_id=tenant_id, rule_id=active_rule.id, biz_stage="FINAL_APPROVED",
                material_code="THESIS_FINAL", material_name="当前规则新名称", owner_role="STUDENT",
                required=True, allowed_ext_json=["pdf"], max_files=1, max_size_bytes=1024,
                version_policy="IMMUTABLE_APPEND", review_required=True, archive_required=True,
                sensitivity_level="SENSITIVE", sort_no=1, enabled=True,
            ),
        ])
        student = GraduationStudent(
            tenant_id=tenant_id, batch_id=batch.id, student_no="FROZEN-001", name="冻结规则学生",
            stage="ARCHIVED", risk_level="NONE", eligibility_status="QUALIFIED",
            grad_qual_status="PASS", record_status="ACTIVE",
        )
        db.add(student); db.flush()
        db.add(GraduationStudentMaterial(
            tenant_id=tenant_id, batch_id=batch.id, gd_student_id=student.id,
            rule_id=frozen_rule.id, rule_version=1, material_code="THESIS_FINAL",
            material_name="历史论文定稿名称", biz_stage="FINAL_APPROVED", owner_role="STUDENT",
            business_status="ARCHIVED", review_status="APPROVED", required_status="REQUIRED",
            archive_status="FROZEN", sensitivity_level="SENSITIVE", migration_status="NATIVE",
        ))
        db.commit()
        student_id = int(student.id)
        frozen_rule_id = int(frozen_rule.id)
    finally:
        db.close()

    result = student_library(student_id, user)
    assert result["ruleId"] == str(frozen_rule_id)
    assert result["ruleVersion"] == 1
    assert result["items"][0]["materialName"] == "历史论文定稿名称"
