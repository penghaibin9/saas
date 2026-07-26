"""补考与清考候选必须消费统一有效成绩，而不是扫描所有历史失败行。"""
from types import SimpleNamespace


def _grade(row_id, score, source, *, name="高等数学"):
    return SimpleNamespace(
        id=row_id,
        acad_student_id=1,
        course_name=name,
        credit_value=4,
        nature="REQUIRED",
        source=source,
        exam_type="NORMAL",
        course_id=None,
        course_code=None,
        record_status="ACTIVE",
        pass_status="PASSED" if score >= 60 else "FAILED",
        score=score,
    )


def test_makeup_pass_removes_old_failure_from_candidates():
    from app.modules.academic_affairs.services.academic_affairs_makeup_facade import (
        _effective_failed_rows,
    )

    rows = [_grade(1, 50, "PUBLISH"), _grade(2, 60, "MAKEUP")]

    assert _effective_failed_rows(rows) == []


def test_failed_makeup_remains_candidate_for_later_policy():
    from app.modules.academic_affairs.services.academic_affairs_makeup_facade import (
        _effective_failed_rows,
    )

    rows = [_grade(1, 50, "PUBLISH"), _grade(2, 55, "MAKEUP")]
    selected = _effective_failed_rows(rows)

    assert len(selected) == 1
    assert selected[0].source == "MAKEUP"
    assert selected[0].score == 55


def test_clearance_pass_removes_all_previous_failures():
    from app.modules.academic_affairs.services.academic_affairs_makeup_facade import (
        _effective_failed_rows,
    )

    rows = [
        _grade(1, 50, "PUBLISH"),
        _grade(2, 55, "MAKEUP"),
        _grade(3, 60, "CLEARANCE"),
    ]

    assert _effective_failed_rows(rows) == []


def test_different_course_identity_is_not_accidentally_removed():
    from app.modules.academic_affairs.services.academic_affairs_makeup_facade import (
        _effective_failed_rows,
    )

    rows = [
        _grade(1, 50, "PUBLISH", name="高等数学"),
        _grade(2, 60, "MAKEUP", name="大学英语"),
    ]
    selected = _effective_failed_rows(rows)

    assert len(selected) == 1
    assert selected[0].course_name == "高等数学"


def test_original_clearance_scan_uses_unified_candidate_function():
    from app.modules.academic_affairs.services import academic_affairs_makeup_facade as service

    assert service._legacy._clearance_candidates is service._clearance_candidates
