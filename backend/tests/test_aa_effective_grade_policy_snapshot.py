"""P0-11：有效成绩课程身份、规则快照与来源回链合同。"""
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]


def _grade(row_id, *, course_id=None, course_code=None, version=None, source="PUBLISH", attempt=1):
    return SimpleNamespace(
        id=row_id,
        tenant_id=1,
        acad_student_id=9,
        course_id=course_id,
        course_code=course_code,
        course_version=version,
        attempt_no=attempt if course_id or course_code else None,
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
    assert policy["identityOrder"] == ["COURSE_CODE", "COURSE_ID", "LEGACY_NAME_KEY"]
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


def test_same_course_code_across_versions_is_one_course_truth():
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        grade_identity_key,
        resolve_effective_grade,
    )

    old_version = _grade(1, course_id=101, course_code="MATH", version=1, attempt=1)
    new_version = _grade(2, course_id=202, course_code="math", version=2, attempt=2)

    assert grade_identity_key(old_version) == grade_identity_key(new_version)
    selected = resolve_effective_grade([old_version, new_version], strategy="LATEST_ATTEMPT")
    assert [row.id for row in selected] == [2]


def test_model_registers_named_same_transaction_listeners_once_and_filters_irrelevant_updates():
    source = (ROOT / "backend/app/models/academic_affairs_effective_grade.py").read_text(encoding="utf-8")
    compat = (ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_effective_grade_policy_compat.py").read_text(encoding="utf-8")

    assert 'event.contains(AcademicGrade, "after_insert", _after_grade_insert)' in source
    assert 'event.contains(AcademicGrade, "after_update", _after_grade_update)' in source
    assert 'event.listen(AcademicGrade, "after_insert", _after_grade_insert)' in source
    assert 'event.listen(AcademicGrade, "after_update", _after_grade_update)' in source
    assert "lambda _m, conn, target" not in source
    assert "history.has_changes()" in source
    assert "connection.execute(table.insert().values" in source
    assert 'event_key = f"{event_type}:{source_biz_type}:{int(source_biz_id)}"' in source
    assert "policy_hash" in source
    assert "LEGACY_NAME_KEY" in source
    assert 'event.remove(AcademicGrade, "before_insert", _grade_model._before_grade_insert)' in compat
    assert 'event.listen(AcademicGrade, "before_insert", _chronological_before_grade_insert)' in compat


def test_migration_chains_after_r11_without_historical_guessing():
    source = (ROOT / "backend/alembic/versions/0132_aa_effective_grade_policy_snapshot.py").read_text(encoding="utf-8")

    assert 'down_revision = "0131_aa_real_semester_pilot"' in source
    assert 'revision = "0132_aa_effective_grade_policy"' in source
    assert "t_aa_effective_grade_policy_snapshot" in source
    assert "历史成绩不回填、不按课程名猜测" in source


def test_makeup_and_clearance_use_exact_source_business_record_in_canonical_service():
    source = (ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_makeup_service.py").read_text(encoding="utf-8")

    assert 'AcademicGrade.source_biz_type == identity["sourceBizType"]' in source
    assert 'AcademicGrade.source_biz_id == identity["sourceBizId"]' in source
    assert 'source_biz_type=identity["sourceBizType"]' in source
    assert 'source_biz_id=identity["sourceBizId"]' in source
    assert '"originGradeId": str(grade.id)' in source


def test_recheck_uses_unified_identity_and_append_only_correction_chain():
    source = (ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_grade_recheck_service.py").read_text(encoding="utf-8")

    assert "mobile_student_identity_facade import resolve_student" in source
    assert "resolve_student(db, get_current_user_ctx() or {})" in source
    assert "profile = _resolve_student(db)" in source
    assert "corrected = AcademicGrade(" in source
    assert 'source_biz_type="RECHECK"' in source
    assert "source_biz_id=row.id" in source
    assert 'grade.record_status = "SUPERSEDED"' in source
    assert "AaGradeCorrection(" in source
    assert "StudentProfile.student_no ==" not in source


def test_canonical_grade_service_debt_includes_policy_snapshot_and_legacy_debt():
    source = (ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_grade_service.py").read_text(encoding="utf-8")

    assert "def identity_debt(user, term=None)" in source
    assert '"missingPolicySnapshot": policy["missingPolicySnapshot"]' in source
    assert '"legacyNameKey": policy["legacyNameKey"]' in source
    assert '"policyReady": policy["ready"]' in source
    assert "grade_identity_debt(db, term=term)" in source
    assert "policy_snapshot_debt(db, term=term)" in source
