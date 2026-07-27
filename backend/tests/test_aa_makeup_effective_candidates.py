"""补考与清考候选必须消费统一有效成绩，而不是扫描所有历史失败行。"""
from types import SimpleNamespace


def _grade(row_id, score, source, *, course_id=101, attempt_no=1):
    return SimpleNamespace(
        id=row_id,
        acad_student_id=1,
        course_name=f"课程{course_id}",
        credit_value=4,
        nature="REQUIRED",
        source=source,
        exam_type=source if source in {"MAKEUP", "CLEARANCE", "DEFERRED"} else "FINAL",
        course_id=course_id,
        course_code=f"C{course_id}",
        course_version=1,
        attempt_no=attempt_no,
        record_status="ACTIVE",
        pass_status="PASSED" if score >= 60 else "FAILED",
        score=score,
    )


def test_makeup_pass_removes_old_failure_from_candidates():
    from app.modules.academic_affairs.services.academic_affairs_makeup_service import _effective_failed_rows

    rows = [_grade(1, 50, "PUBLISH"), _grade(2, 60, "MAKEUP")]
    assert _effective_failed_rows(rows) == []


def test_failed_makeup_remains_candidate_for_later_policy():
    from app.modules.academic_affairs.services.academic_affairs_makeup_service import _effective_failed_rows

    rows = [_grade(1, 50, "PUBLISH"), _grade(2, 55, "MAKEUP")]
    selected = _effective_failed_rows(rows)

    assert len(selected) == 1
    assert selected[0].source == "MAKEUP"
    assert selected[0].score == 55


def test_clearance_pass_removes_all_previous_failures():
    from app.modules.academic_affairs.services.academic_affairs_makeup_service import _effective_failed_rows

    rows = [
        _grade(1, 50, "PUBLISH"),
        _grade(2, 55, "MAKEUP"),
        _grade(3, 60, "CLEARANCE"),
    ]
    assert _effective_failed_rows(rows) == []


def test_different_course_identity_is_not_accidentally_removed():
    from app.modules.academic_affairs.services.academic_affairs_makeup_service import _effective_failed_rows

    rows = [
        _grade(1, 50, "PUBLISH", course_id=101),
        _grade(2, 60, "MAKEUP", course_id=202),
    ]
    selected = _effective_failed_rows(rows)

    assert len(selected) == 1
    assert selected[0].course_id == 101


def test_new_study_attempt_replaces_old_attempt_even_with_lower_source_priority():
    from app.modules.academic_affairs.services.academic_affairs_makeup_service import _effective_failed_rows

    rows = [
        _grade(9, 60, "CLEARANCE", attempt_no=1),
        _grade(2, 50, "PUBLISH", attempt_no=2),
    ]
    selected = _effective_failed_rows(rows)

    assert len(selected) == 1
    assert selected[0].attempt_no == 2
    assert selected[0].score == 50


def test_legacy_makeup_facade_only_reexports_canonical_candidate_function():
    from app.modules.academic_affairs.services import academic_affairs_makeup_facade as compatibility
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as canonical

    assert compatibility._legacy is canonical
    assert compatibility._effective_failed_rows is canonical._effective_failed_rows
    assert compatibility.makeup_pending is canonical.makeup_pending
