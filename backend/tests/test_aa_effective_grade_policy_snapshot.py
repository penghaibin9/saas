"""P0-11：有效成绩课程身份、规则快照与来源回链合同。"""
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]


def _grade(row_id, *, course_id=None, course_code=None, version=None, source="PUBLISH"):
    return SimpleNamespace(
        id=row_id,
        tenant_id=1,
        acad_student_id=9,
        course_id=course_id,
        course_code=course_code,
        course_version=version,
        attempt_no=1 if course_id or course_code else None,
        course_name="高等数学",
        nature="REQUIRED",
        credit_value=4,
        score=80,
        pass_status="PASSED",
        record_status="ACTIVE",
        exam_type="FINAL",
        source=source,
    )


def test_policy_explicitly_forbids_legacy_name_merge_and_score_comparison():
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        policy_payload,
    )

    policy = policy_payload()

    assert policy["legacyMerge"] == "NEVER"
    assert policy["scoreComparison"] == "DISABLED"
    assert policy["identityOrder"] == ["COURSE_ID", "COURSE_CODE", "LEGACY_NAME_KEY"]
    assert policy["sourcePriority"]["RECHECK"] > policy["sourcePriority"]["PUBLISH"]


def test_legacy_rows_get_distinct_identity_even_when_display_fields_match():
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        grade_identity_key,
        resolve_effective_grade,
    )

    first = _grade(1)
    second = _grade(2)

    assert grade_identity_key(first)[1] == "LEGACY_NAME_KEY"
    assert grade_identity_key(first) != grade_identity_key(second)
    assert {row.id for row in resolve_effective_grade([first, second])} == {1, 2}


def test_stable_course_identity_allows_formal_source_resolution_without_using_score():
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        resolve_effective_grade,
    )

    original = _grade(1, course_id=101, course_code="MATH", version=2, source="PUBLISH")
    original.score = 99
    recheck = _grade(2, course_id=101, course_code="MATH", version=2, source="RECHECK")
    recheck.score = 61

    selected = resolve_effective_grade([original, recheck])

    assert len(selected) == 1
    assert selected[0].id == 2
    assert selected[0].score == 61


def test_model_registers_same_transaction_insert_and_update_listeners():
    source = (ROOT / "backend/app/models/academic_affairs_effective_grade.py").read_text(encoding="utf-8")

    assert 'event.listen(AcademicGrade, "after_insert"' in source
    assert 'event.listen(AcademicGrade, "after_update"' in source
    assert "connection.execute(table.insert().values" in source
    assert "policy_hash" in source
    assert "LEGACY_NAME_KEY" in source


def test_migration_chains_after_r11_without_historical_guessing():
    source = (ROOT / "backend/alembic/versions/0132_aa_effective_grade_policy_snapshot.py").read_text(encoding="utf-8")

    assert 'down_revision = "0131_aa_real_semester_pilot"' in source
    assert 'revision = "0132_aa_effective_grade_policy"' in source
    assert "t_aa_effective_grade_policy_snapshot" in source
    assert "历史成绩不回填、不按课程名猜测" in source


def test_makeup_and_clearance_use_exact_source_business_record():
    source = (ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_makeup_grade_identity_facade.py").read_text(encoding="utf-8")

    assert 'AcademicGrade.source_biz_type == source' in source
    assert 'AcademicGrade.source_biz_id == makeup.id' in source
    assert 'source_biz_type=source' in source
    assert 'source_biz_id=makeup.id' in source
    assert "makeup.origin_grade_id = origin.id" in source


def test_recheck_uses_unified_student_identity_and_exact_source_link():
    source = (ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_grade_recheck_service.py").read_text(encoding="utf-8")

    assert "mobile_student_identity_facade import resolve_student" in source
    assert 'grade.source_biz_type = "RECHECK"' in source
    assert "grade.source_biz_id = row.id" in source
    assert "StudentProfile.student_no ==" not in source


def test_public_grade_debt_includes_policy_snapshot_and_legacy_debt():
    source = (ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_grade_policy_facade.py").read_text(encoding="utf-8")
    public_init = (ROOT / "backend/app/modules/academic_affairs/services/__init__.py").read_text(encoding="utf-8")

    assert "missingPolicySnapshot" in source
    assert "legacyNameKey" in source
    assert "policyReady" in source
    assert "_original_identity_debt" in source
    assert "academic_affairs_grade_policy_facade as academic_affairs_grade_service" in public_init
