"""P0-05/P0-11：学生选课身份与先修课程稳定代码合同。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICES = ROOT / "backend/app/modules/academic_affairs/services"


def test_selection_student_guard_uses_account_binding_and_course_code():
    canonical = (SERVICES / "academic_affairs_selection_service.py").read_text(encoding="utf-8")
    core = (SERVICES / "academic_affairs_selection_core_service.py").read_text(encoding="utf-8")
    compatibility = (SERVICES / "academic_affairs_selection_student_guard.py").read_text(encoding="utf-8")

    assert "mobile_student_identity_facade import resolve_student" in canonical
    assert "student = resolve_student(db, get_current_user_ctx() or {})" in canonical
    assert "academic_affairs_selection_authority_consumer import passed_course_codes" in canonical
    assert "academic_affairs_selection_authority_consumer import passed_course_names" in core
    assert "source_course = catalog_by_id[int(course.course_id)]" in canonical
    assert "target_code in passed_codes" in canonical
    assert "prerequisites - passed_codes" in canonical
    assert "AcademicGrade" not in canonical
    assert "AcademicStudent" not in canonical
    assert "AcademicGrade" not in core
    assert "AcademicStudent" not in core
    assert "StudentProfile.student_no ==" not in canonical
    assert "course_name in passed" not in canonical

    # 历史 guard 只保留导入兼容，不再复制/覆盖第二套身份和先修逻辑。
    assert "_canonical._load_student" in compatibility
    assert "_canonical._validate_enroll" in compatibility
    assert "def _validate_enroll" not in compatibility


def test_selection_guard_preserves_original_capacity_and_conflict_controls():
    canonical = (SERVICES / "academic_affairs_selection_service.py").read_text(encoding="utf-8")
    core = (SERVICES / "academic_affairs_selection_core_service.py").read_text(encoding="utf-8")
    final = (SERVICES / "academic_affairs_selection_final_service.py").read_text(encoding="utf-8")

    assert "_weeks_overlap" in canonical
    assert "maxCredits" in canonical
    assert "allow_reselect_closed" in canonical
    assert "course.selected_count" in canonical
    assert "academic_affairs_selection_authority_consumer import task_slots" in core
    # stable-courseCode 的 final write path 必须保留冲突审计后再拒绝。
    assert "_base._core._record_conflict_reject" in final
    assert '"上课时间冲突"' in final
    assert "_base._validate_enroll(" in final


def test_guard_is_loaded_after_selection_facade():
    package = (SERVICES / "__init__.py").read_text(encoding="utf-8")
    compatibility = (SERVICES / "academic_affairs_selection_student_guard.py").read_text(encoding="utf-8")

    # 当前架构由包级入口直接选择 final service；兼容 guard 不再依赖 import-order 安装。
    assert "academic_affairs_selection_final_service as academic_affairs_selection_service" in package
    assert "academic_affairs_selection_student_guard" not in package
    assert "_canonical =" in compatibility or "as _canonical" in compatibility
    assert "install(" not in compatibility
    assert "._validate_enroll =" not in compatibility
