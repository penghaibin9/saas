"""P0-05：学生自助旧入口必须安装统一账号身份守卫。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_level_exam_guard_replaces_token_student_number_lookup():
    source = _read("backend/app/modules/academic_affairs/services/academic_affairs_level_exam_identity_guard.py")

    assert "mobile_student_identity_facade import resolve_student" in source
    assert "_base._student_profile = _student_profile" in source


def test_major_split_guard_replaces_token_student_number_lookup():
    source = _read("backend/app/modules/academic_affairs/services/academic_affairs_major_split_identity_guard.py")

    assert "mobile_student_identity_facade import resolve_student" in source
    assert "_base._student_profile = _student_profile" in source


def test_selection_guard_ignores_legacy_student_number_argument():
    source = _read("backend/app/modules/academic_affairs/services/academic_affairs_selection_student_guard.py")

    assert "return resolve_student(db, get_current_user_ctx() or {})" in source
    assert "student_no" in source  # kept only for call compatibility
    assert "StudentProfile.student_no ==" not in source


def test_selection_passed_and_prerequisite_rules_use_course_code():
    source = _read("backend/app/modules/academic_affairs/services/academic_affairs_selection_student_guard.py")

    assert "_passed_course_codes" in source
    assert "resolve_effective_grade" in source
    assert "target_code in passed_codes" in source
    assert "prerequisite_codes - passed_codes" in source
    assert "target.course_name in passed" not in source


def test_all_guards_are_loaded_by_academic_service_package():
    source = _read("backend/app/modules/academic_affairs/services/__init__.py")

    for module in (
        "academic_affairs_level_exam_identity_guard",
        "academic_affairs_major_split_identity_guard",
        "academic_affairs_selection_student_guard",
        "academic_affairs_recognition_identity_guard",
    ):
        assert module in source
