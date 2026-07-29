"""P0-05/P0-11：学生选课身份与先修课程稳定代码合同。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_selection_student_guard_uses_account_binding_and_course_code():
    source = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_selection_student_guard.py"
    ).read_text(encoding="utf-8")

    assert "mobile_student_identity_facade import resolve_student" in source
    assert "return resolve_student(db, get_current_user_ctx() or {})" in source
    assert "resolve_effective_grade(rows)" in source
    assert "target_code in passed_codes" in source
    assert "prerequisite_codes - passed_codes" in source
    assert "StudentProfile.student_no ==" not in source
    assert "course_name in passed" not in source


def test_selection_guard_preserves_original_capacity_and_conflict_controls():
    source = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_selection_student_guard.py"
    ).read_text(encoding="utf-8")

    assert "_weeks_overlap" in source
    assert "_record_conflict_reject" in source
    assert "maxCredits" in source
    assert "allow_reselect_closed" in source
    assert "_legacy._validate_enroll = _validate_enroll" in source


def test_guard_is_loaded_after_selection_facade():
    source = (
        ROOT / "backend/app/modules/academic_affairs/services/__init__.py"
    ).read_text(encoding="utf-8")

    facade_index = source.index("academic_affairs_selection_facade as academic_affairs_selection_service")
    guard_index = source.index("academic_affairs_selection_student_guard")
    assert guard_index > facade_index
