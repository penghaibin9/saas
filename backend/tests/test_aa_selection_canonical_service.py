"""选课正式 Service、轮次摇号和名单锁定契约。"""
from pathlib import Path
from types import SimpleNamespace


def test_public_selection_services_are_canonical():
    from app.modules.academic_affairs.services import (
        academic_affairs_selection_round_service as rounds,
        academic_affairs_selection_service as selection,
    )

    assert selection.__name__.endswith("academic_affairs_selection_service")
    assert selection._core.__name__.endswith("academic_affairs_selection_core_service")
    assert rounds.__name__.endswith("academic_affairs_selection_round_service")
    assert rounds._core.__name__.endswith("academic_affairs_selection_round_core_service")
    for name in (
        "create_batch", "student_enroll", "student_drop", "lock_batch",
        "adjust_record", "archive_batch",
    ):
        assert callable(getattr(selection, name))
    for name in ("create_round", "open_round", "close_round", "draw_round"):
        assert callable(getattr(rounds, name))


def test_lottery_order_is_cross_process_deterministic():
    from app.modules.academic_affairs.services.academic_affairs_selection_round_service import _draw_key

    first = [_draw_key(9, value) for value in (5, 2, 8, 1)]
    second = [_draw_key(9, value) for value in (5, 2, 8, 1)]

    assert first == second
    assert len(set(first)) == 4
    assert _draw_key(9, 5) != _draw_key(10, 5)


def test_student_identity_uses_unified_binding(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_selection_service as service
    from app.services import mobile_student_identity_facade as identity

    student = SimpleNamespace(id=12, student_no="20260012")
    calls = []
    monkeypatch.setattr(
        identity,
        "resolve_student",
        lambda db, user: calls.append((db, user)) or student,
    )
    monkeypatch.setattr(service, "get_current_user_ctx", lambda: {"userId": "db-77"})
    db = object()

    assert service._load_student(db) is student
    assert calls == [(db, {"userId": "db-77"})]


def test_legacy_selection_facades_only_reexport_canonical_services():
    from app.modules.academic_affairs.services import (
        academic_affairs_selection_facade as compatibility,
        academic_affairs_selection_round_facade as round_compatibility,
        academic_affairs_selection_round_service as rounds,
        academic_affairs_selection_service as selection,
        academic_affairs_selection_student_guard as student_compatibility,
    )

    assert compatibility._legacy is selection
    assert compatibility.lock_batch is selection.lock_batch
    assert compatibility.adjust_record is selection.adjust_record
    assert student_compatibility._legacy is selection
    assert student_compatibility._validate_enroll is selection._validate_enroll
    assert round_compatibility._legacy is rounds
    assert round_compatibility.draw_round is rounds.draw_round


def test_selection_source_uses_course_code_and_effective_grades_not_course_name():
    source = (
        Path(__file__).resolve().parents[1]
        / "app/modules/academic_affairs/services/academic_affairs_selection_service.py"
    ).read_text(encoding="utf-8")

    assert "grade_service.effective_grade_rows" in source
    assert "target.course_code" in source
    assert "target.prerequisite_codes_json" in source
    assert "该课程已通过，不可再选" in source
    assert "AcademicGrade.course_name ==" not in source


def test_locked_adjustment_uses_exact_r9_consumers_and_new_roster_version():
    source = (
        Path(__file__).resolve().parents[1]
        / "app/modules/academic_affairs/services/academic_affairs_selection_service.py"
    ).read_text(encoding="utf-8")

    assert "consumer_counts(db, teaching_class_id=int(teaching_class.id))" in source
    assert "project_selection_course_locked" in source
    assert "正式名单已被考勤、考务或成绩使用" in source
    assert "course_name ==" not in source


def test_lock_batch_validates_then_atomically_projects_roster():
    source = (
        Path(__file__).resolve().parents[1]
        / "app/modules/academic_affairs/services/academic_affairs_selection_service.py"
    ).read_text(encoding="utf-8")

    assert "validate_selection_lock(db, batch)" in source
    assert "selectedRecordCount" in source
    assert "apply_locked_roster_projection(db, validation)" in source
    assert source.index("validate_selection_lock(db, batch)") < source.index("apply_locked_roster_projection(db, validation)")


def test_round_draw_does_not_use_python_hash():
    source = (
        Path(__file__).resolve().parents[1]
        / "app/modules/academic_affairs/services/academic_affairs_selection_round_service.py"
    ).read_text(encoding="utf-8")

    assert "hashlib.sha256" in source
    assert "SHA256_ROUND_RECORD_V1" in source
    assert "hash((" not in source
