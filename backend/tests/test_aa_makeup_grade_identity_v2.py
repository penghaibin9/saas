"""V2-04 补考/清考正式成绩身份回归。"""
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_public_makeup_service_is_grade_identity_facade():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_makeup_service.__name__.endswith(
        "academic_affairs_makeup_grade_identity_facade"
    )
    assert services.academic_affairs_makeup_service._base.__name__.endswith(
        "academic_affairs_makeup_identity_facade"
    )
    assert services.academic_affairs_makeup_service.finish_makeup_batch.__module__.endswith(
        "academic_affairs_makeup_grade_identity_facade"
    )
    assert services.academic_affairs_makeup_service._legacy.finish_makeup_batch is services.academic_affairs_makeup_service.finish_makeup_batch


def test_origin_failed_grade_requires_unique_effective_identity(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_makeup_grade_identity_facade as service

    rows = [
        SimpleNamespace(
            id=1, acad_student_id=9, course_name="大学英语", course_id=101,
            course_code="ENG101", course_version=1, attempt_no=1,
            pass_status="FAILED", record_status="ACTIVE", source="PUBLISH",
        ),
        SimpleNamespace(
            id=2, acad_student_id=9, course_name="大学英语", course_id=202,
            course_code="ENG201", course_version=1, attempt_no=1,
            pass_status="FAILED", record_status="ACTIVE", source="PUBLISH",
        ),
    ]

    class _Scalars:
        def all(self):
            return rows

    class _Db:
        def scalars(self, _query):
            return _Scalars()

    monkeypatch.setattr(service._grade, "effective_grade_rows", lambda values: list(values))
    with pytest.raises(AppException) as exc:
        service._origin_failed_grade(_Db(), SimpleNamespace(acad_student_id=9, course_name="大学英语"))
    assert "无法唯一定位" in exc.value.message


def test_origin_failed_grade_rejects_legacy_identity(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_makeup_grade_identity_facade as service

    legacy = SimpleNamespace(
        id=7, acad_student_id=9, course_name="高等数学", course_id=None,
        course_code=None, course_version=None, attempt_no=None,
        pass_status="FAILED", record_status="ACTIVE", source="LEGACY",
    )

    class _Scalars:
        def all(self):
            return [legacy]

    class _Db:
        def scalars(self, _query):
            return _Scalars()

    monkeypatch.setattr(service._grade, "effective_grade_rows", lambda values: list(values))
    with pytest.raises(AppException) as exc:
        service._origin_failed_grade(_Db(), SimpleNamespace(acad_student_id=9, course_name="高等数学"))
    assert "缺少courseId" in exc.value.message


def test_makeup_publish_source_inherits_identity_and_attempt_without_increment():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "app/modules/academic_affairs/services/academic_affairs_makeup_grade_identity_facade.py"
    )
    source = source_path.read_text(encoding="utf-8")
    for text in (
        "course_id=origin.course_id",
        "course_code=origin.course_code",
        "course_version=origin.course_version",
        "attempt_no=attempt_no",
        "grade_task_id=origin.grade_task_id",
        "teaching_task_id=origin.teaching_task_id",
        "teaching_class_id=origin.teaching_class_id",
        "roster_version_id=origin.roster_version_id",
        "source_attempt_no(origin)",
    ):
        assert text in source
    assert "next_study_attempt_no" not in source
    assert "AcademicGrade.course_name == makeup.course_name" not in source


def test_makeup_identity_idempotency_uses_course_attempt_and_source():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "app/modules/academic_affairs/services/academic_affairs_makeup_grade_identity_facade.py"
    )
    source = source_path.read_text(encoding="utf-8")
    assert "AcademicGrade.course_id == origin.course_id" in source
    assert "AcademicGrade.attempt_no == attempt_no" in source
    assert "AcademicGrade.source == source" in source
