"""学生PC/微信重修免修候选必须消费统一有效成绩策略。"""
from pathlib import Path


def test_mobile_makeup_options_do_not_group_by_course_name_or_highest_score():
    root = Path(__file__).resolve().parents[2]
    source = (
        root / "backend/app/modules/academic_affairs/services/mobile_academic_gaps_service.py"
    ).read_text(encoding="utf-8")

    assert "resolve_effective_grade(rows)" in source
    assert "grade_identity_key(g)" in source
    assert '"identityType": identity[1]' in source
    assert '"identityDebt": identity[1] == "LEGACY_NAME_KEY"' in source
    assert "by_course" not in source
    assert "(g.score or -1) >" not in source


def test_student_options_return_exact_course_and_attempt_identity():
    from app.modules.academic_affairs import services

    mobile = services.mobile_academic_affairs_service
    assert callable(mobile.makeup_options_my)
    root = Path(__file__).resolve().parents[2]
    source = (
        root / "backend/app/modules/academic_affairs/services/mobile_academic_gaps_service.py"
    ).read_text(encoding="utf-8")
    for field in ("courseId", "courseCode", "courseVersion", "attemptNo", "gradeId"):
        assert f'"{field}"' in source
    assert "resolve_effective_grade(rows)" in source
    assert "identityDebtCount" in source


def test_recognition_self_service_uses_unified_account_binding_and_source_link():
    from app.modules.academic_affairs import services

    recognition = services.academic_affairs_recognition_service
    source = Path(recognition.__file__).read_text(encoding="utf-8")

    assert "mobile_student_identity_facade import resolve_student" in source
    assert "代录学号命中多份学生档案" in source
    assert 'source_biz_type="RECOGNITION"' in source
    assert "source_biz_id=row.id" in source
    assert "setattr(" not in source
    assert "_base._resolve_student =" not in source


def test_recognition_guard_is_compatibility_export_only():
    root = Path(__file__).resolve().parents[2]
    source = (
        root / "backend/app/modules/academic_affairs/services/academic_affairs_recognition_identity_guard.py"
    ).read_text(encoding="utf-8")

    assert "academic_affairs_recognition_public_service" in source
    assert "_base._resolve_student =" not in source
    assert "_base.review =" not in source
