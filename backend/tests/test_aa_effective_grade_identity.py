"""有效成绩不得按课程名称、最高分或记录插入顺序决定；所有消费者使用同一策略。"""
from types import SimpleNamespace


def _grade(
    row_id,
    score,
    *,
    student=1,
    name="高等数学",
    credit=4,
    nature="REQUIRED",
    source="PUBLISH",
    exam_type="FINAL",
    course_id=None,
    course_code=None,
    course_version=1,
    attempt_no=1,
    record_status="ACTIVE",
):
    return SimpleNamespace(
        id=row_id,
        tenant_id=1,
        is_deleted=False,
        acad_student_id=student,
        course_name=name,
        credit_value=credit,
        nature=nature,
        source=source,
        exam_type=exam_type,
        course_id=course_id,
        course_code=course_code,
        course_version=course_version,
        attempt_no=attempt_no,
        record_status=record_status,
        pass_status="PASSED" if score >= 60 else "FAILED",
        score=score,
    )


def test_same_name_different_course_ids_are_not_merged():
    from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows

    rows = [
        _grade(1, 90, course_id=101),
        _grade(2, 70, course_id=202),
    ]
    assert {row.id for row in effective_grade_rows(rows)} == {1, 2}


def test_legacy_same_name_different_credit_is_not_merged():
    from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows

    rows = [
        _grade(1, 90, credit=2, course_version=None, attempt_no=None),
        _grade(2, 70, credit=4, course_version=None, attempt_no=None),
    ]
    assert {row.id for row in effective_grade_rows(rows)} == {1, 2}


def test_legacy_exact_same_name_nature_and_credit_is_still_not_silently_merged():
    from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import grade_identity_key

    first = _grade(1, 90, course_version=None, attempt_no=None)
    second = _grade(2, 70, course_version=None, attempt_no=None)
    selected = effective_grade_rows([first, second])

    assert {row.id for row in selected} == {1, 2}
    assert grade_identity_key(first)[1] == "LEGACY_NAME_KEY"
    assert grade_identity_key(first) != grade_identity_key(second)


def test_latest_attempt_wins_even_when_id_and_score_are_lower():
    from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows

    old_high_newer_id = _grade(99, 95, course_id=101, attempt_no=1)
    latest_lower_older_id = _grade(2, 61, course_id=101, attempt_no=2)
    selected = effective_grade_rows([old_high_newer_id, latest_lower_older_id])

    assert len(selected) == 1
    assert selected[0].id == 2
    assert selected[0].score == 61


def test_source_priority_applies_inside_same_attempt_without_comparing_score():
    from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows

    original = _grade(20, 99, source="PUBLISH", course_id=101, attempt_no=1)
    makeup = _grade(2, 55, source="MAKEUP", course_id=101, attempt_no=1)
    selected = effective_grade_rows([original, makeup])

    assert selected[0].source == "MAKEUP"
    assert selected[0].score == 55


def test_new_attempt_beats_higher_priority_source_from_old_attempt():
    from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows

    old_recheck = _grade(50, 99, source="RECHECK", course_id=101, attempt_no=1)
    new_publish = _grade(2, 60, source="PUBLISH", course_id=101, attempt_no=2)
    selected = effective_grade_rows([old_recheck, new_publish])

    assert selected[0].id == 2
    assert selected[0].attempt_no == 2


def test_clearance_supersedes_makeup_and_original_in_same_attempt():
    from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows

    original = _grade(1, 58, source="PUBLISH", course_id=101)
    makeup = _grade(2, 59, source="MAKEUP", course_id=101)
    clearance = _grade(3, 60, source="CLEARANCE", course_id=101)
    selected = effective_grade_rows([clearance, original, makeup])

    assert selected[0].source == "CLEARANCE"
    assert selected[0].score == 60


def test_inactive_row_cannot_override_active_row():
    from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows

    active = _grade(1, 60, source="PUBLISH", record_status="ACTIVE", course_id=101)
    voided = _grade(9, 100, source="RECHECK", record_status="VOIDED", course_id=101)
    selected = effective_grade_rows([active, voided])

    assert selected[0].id == 1


def test_aggregate_uses_same_policy_instead_of_old_high_score(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_grade_service as service

    class _Db:
        def scalars(self, _query):
            return SimpleNamespace(all=lambda: [
                _grade(99, 95, credit=4, course_id=101, attempt_no=1),
                _grade(2, 61, credit=4, course_id=101, attempt_no=2),
            ])

    monkeypatch.setattr(service._core, "_tid", lambda: 1)
    academic_student = SimpleNamespace(
        id=1,
        avg_score=None,
        failed_count=None,
        obtained_credits=None,
        gpa=None,
    )
    service._refresh_aggregates(_Db(), academic_student)

    assert academic_student.avg_score == 61
    assert academic_student.failed_count == 0
    assert academic_student.obtained_credits == 4
    assert academic_student.gpa == 1.1


def test_legacy_facade_is_side_effect_free_compatibility_only():
    from app.modules.academic_affairs.services import academic_affairs_grade_facade as compatibility
    from app.modules.academic_affairs.services import academic_affairs_grade_service as canonical
    from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_service as policy

    assert compatibility._legacy is canonical
    assert compatibility.effective_grade_rows is canonical.effective_grade_rows
    assert compatibility.refresh_academic_aggregates is canonical._refresh_aggregates
    assert compatibility.grade_identity_key is policy.grade_identity_key
