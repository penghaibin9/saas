"""P0-05：学生自助旧入口必须使用统一账号身份，且兼容层不得 monkey patch。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_level_exam_identity_is_in_canonical_service():
    service = _read("backend/app/modules/academic_affairs/services/academic_affairs_level_exam_service.py")
    guard = _read("backend/app/modules/academic_affairs/services/academic_affairs_level_exam_identity_guard.py")

    assert "mobile_student_identity_facade import resolve_student" in service
    assert "StudentProfile.student_no ==" not in service
    assert "_base._student_profile =" not in guard
    assert "_canonical._student_profile" in guard


def test_major_split_uses_side_effect_free_public_service():
    public_service = _read(
        "backend/app/modules/academic_affairs/services/academic_affairs_major_split_public_service.py"
    )
    guard = _read("backend/app/modules/academic_affairs/services/academic_affairs_major_split_identity_guard.py")
    package = _read("backend/app/modules/academic_affairs/services/__init__.py")

    assert "mobile_student_identity_facade import resolve_student" in public_service
    assert "student_id == profile.id" in public_service
    assert "with_for_update" in public_service
    assert "_base._student_profile =" not in guard
    assert "academic_affairs_major_split_public_service as academic_affairs_major_split_service" in package


def test_selection_guard_is_only_a_compatibility_export():
    source = _read("backend/app/modules/academic_affairs/services/academic_affairs_selection_student_guard.py")

    assert "_canonical._load_student" in source
    assert "StudentProfile.student_no ==" not in source
    assert "_base._" not in source


def test_selection_passed_and_prerequisite_rules_use_course_code():
    source = _read("backend/app/modules/academic_affairs/services/academic_affairs_selection_service.py")

    assert "_passed_course_codes" in source
    assert "effective_grade_rows" in source
    assert "target_code in passed_codes" in source
    assert "prerequisites - passed_codes" in source
    assert "target.course_name in passed" not in source


def test_identity_compatibility_modules_have_no_function_replacement():
    for path in (
        "backend/app/modules/academic_affairs/services/academic_affairs_level_exam_identity_guard.py",
        "backend/app/modules/academic_affairs/services/academic_affairs_major_split_identity_guard.py",
        "backend/app/modules/academic_affairs/services/academic_affairs_selection_student_guard.py",
        "backend/app/modules/academic_affairs/services/academic_affairs_recognition_identity_guard.py",
    ):
        source = _read(path)
        assert "sys.modules" not in source
        assert "__dict__.update" not in source
        assert "._student_profile =" not in source
