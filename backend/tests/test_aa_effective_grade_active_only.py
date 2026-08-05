"""P0-3/P0-4：整组已被更正或作废的成绩不得重新参与学分、GPA和先修判断。"""
from types import SimpleNamespace


def _row(row_id, status):
    return SimpleNamespace(
        id=row_id,
        acad_student_id=1,
        course_id=100 + row_id,
        course_code="SAME_COURSE",
        course_version=row_id,
        attempt_no=row_id,
        score=80,
        pass_status="PASSED",
        record_status=status,
        source="RECHECK",
        exam_type="FINAL",
        effective_attempt_strategy="LATEST_ATTEMPT",
    )


def test_group_with_no_active_grade_is_not_effective():
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        resolve_effective_grade,
    )

    assert resolve_effective_grade([
        _row(1, "SUPERSEDED"),
        _row(2, "VOID"),
    ]) == []


def test_active_correction_is_selected_and_superseded_original_is_ignored():
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        resolve_effective_grade,
    )

    rows = [_row(1, "SUPERSEDED"), _row(2, "ACTIVE")]
    selected = resolve_effective_grade(rows)
    assert [row.id for row in selected] == [2]
