"""有效成绩不得再按课程名称取最高分。"""
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
    record_status="ACTIVE",
):
    return SimpleNamespace(
        id=row_id,
        acad_student_id=student,
        course_name=name,
        credit_value=credit,
        nature=nature,
        source=source,
        exam_type=exam_type,
        course_id=course_id,
        course_code=course_code,
        record_status=record_status,
        pass_status="PASSED" if score >= 60 else "FAILED",
        score=score,
    )


def test_same_name_different_course_ids_are_not_merged():
    from app.modules.academic_affairs.services.academic_affairs_grade_facade import effective_grade_rows

    rows = [
        _grade(1, 90, course_id=101),
        _grade(2, 70, course_id=202),
    ]

    assert {row.id for row in effective_grade_rows(rows)} == {1, 2}


def test_legacy_same_name_different_credit_is_not_merged():
    from app.modules.academic_affairs.services.academic_affairs_grade_facade import effective_grade_rows

    rows = [
        _grade(1, 90, credit=2),
        _grade(2, 70, credit=4),
    ]

    assert {row.id for row in effective_grade_rows(rows)} == {1, 2}


def test_latest_official_attempt_wins_even_when_score_is_lower():
    from app.modules.academic_affairs.services.academic_affairs_grade_facade import effective_grade_rows

    old_high = _grade(1, 95)
    latest_lower = _grade(2, 61)

    selected = effective_grade_rows([old_high, latest_lower])

    assert len(selected) == 1
    assert selected[0].id == 2
    assert selected[0].score == 61


def test_formal_recheck_source_beats_plain_publish_without_comparing_score():
    from app.modules.academic_affairs.services.academic_affairs_grade_facade import effective_grade_rows

    rechecked = _grade(3, 58, source="RECHECK")
    published = _grade(9, 99, source="PUBLISH")

    selected = effective_grade_rows([published, rechecked])

    assert selected[0].id == 3
    assert selected[0].score == 58


def test_inactive_row_cannot_override_active_row():
    from app.modules.academic_affairs.services.academic_affairs_grade_facade import effective_grade_rows

    active = _grade(1, 60, source="PUBLISH", record_status="ACTIVE")
    voided = _grade(9, 100, source="RECHECK", record_status="VOIDED")

    selected = effective_grade_rows([active, voided])

    assert selected[0].id == 1
