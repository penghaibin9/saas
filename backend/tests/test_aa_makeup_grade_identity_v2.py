"""V2-04 补考、清考、缓考正式成绩身份回归。"""
from pathlib import Path
from types import SimpleNamespace

import pytest


def _grade(row_id, *, course_id=101, attempt_no=1, passed=False):
    return SimpleNamespace(
        id=row_id,
        acad_student_id=9,
        course_id=course_id,
        course_code=f"C{course_id}",
        course_version=1,
        attempt_no=attempt_no,
        course_name=f"课程{course_id}",
        pass_status="PASSED" if passed else "FAILED",
        record_status="ACTIVE",
        source="PUBLISH",
        exam_type="FINAL",
        nature="REQUIRED",
        credit_value=3,
        grade_task_id=8,
        teaching_task_id=18,
        teaching_class_id=28,
        roster_version_id=38,
    )


def test_public_makeup_service_is_canonical_and_side_effect_free():
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as service

    assert service.__name__.endswith("academic_affairs_makeup_service")
    assert service._core.__name__.endswith("academic_affairs_makeup_core_service")
    assert callable(service.makeup_pending)
    assert callable(service.enroll_makeup_by_grade)
    assert callable(service.finish_makeup_batch)
    assert callable(service.merge_deferred)
    assert callable(service.retake_enroll)
    assert callable(service.exemption_review)


def test_effective_failed_grade_uses_exact_grade_id(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as service

    rows = [_grade(1, course_id=101), _grade(2, course_id=202)]

    class _Query:
        def filter(self, *_args):
            return self

        def all(self):
            return rows

    class _Db:
        def query(self, _model):
            return _Query()

    monkeypatch.setattr(service._core, "_tid", lambda: 1)
    selected = service._effective_failed_grade(_Db(), 9, 2)
    assert selected.id == 2
    assert selected.course_id == 202

    with pytest.raises(AppException) as exc:
        service._effective_failed_grade(_Db(), 9, 99)
    assert "已不是当前有效挂科结果" in exc.value.message


def test_effective_failed_grade_rejects_legacy_identity(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as service

    legacy = _grade(7)
    legacy.course_id = None
    legacy.course_code = None
    legacy.course_version = None
    legacy.attempt_no = None

    class _Query:
        def filter(self, *_args):
            return self

        def all(self):
            return [legacy]

    class _Db:
        def query(self, _model):
            return _Query()

    monkeypatch.setattr(service._core, "_tid", lambda: 1)
    monkeypatch.setattr(service.grade_service, "effective_grade_rows", lambda values: list(values))
    with pytest.raises(AppException) as exc:
        service._effective_failed_grade(_Db(), 9, 7)
    assert "缺少courseId" in exc.value.message


def test_academic_makeup_model_has_deferred_source_and_roster_identity():
    from app.models import AcademicMakeup

    fields = set(AcademicMakeup.__mapper__.attrs.keys())
    assert {
        "origin_grade_id", "source_biz_type", "source_biz_id",
        "course_id", "course_code", "course_version", "attempt_no",
        "teaching_task_id", "teaching_class_id", "roster_version_id",
    } <= fields
    unique_names = {
        constraint.name for constraint in AcademicMakeup.__table__.constraints
        if constraint.name
    }
    assert "uk_acad_makeup_source_biz" in unique_names


def test_makeup_publish_inherits_attempt_and_freezes_policy_snapshot():
    source = (
        Path(__file__).resolve().parents[1]
        / "app/modules/academic_affairs/services/academic_affairs_makeup_service.py"
    ).read_text(encoding="utf-8")

    for text in (
        '"attemptNo": int(origin.attempt_no)',
        '"teachingTaskId": origin.teaching_task_id',
        '"teachingClassId": origin.teaching_class_id',
        '"rosterVersionId": origin.roster_version_id',
        "freeze_effective_grade_policy(",
        'source_biz_type=identity["sourceBizType"]',
        'source_biz_id=identity["sourceBizId"]',
    ):
        assert text in source
    assert "AcademicGrade.course_name ==" not in source


def test_deferred_merge_requires_exam_course_frozen_roster():
    source = (
        Path(__file__).resolve().parents[1]
        / "app/modules/academic_affairs/services/academic_affairs_makeup_service.py"
    ).read_text(encoding="utf-8")

    assert 'get_consumer_snapshot(db, "EXAM_COURSE"' in source
    assert 'source_biz_type="DEFERRED_EXAM"' in source
    assert 'kind="DEFERRED"' in source
    assert "禁止按当前行政班猜测" in source


def test_0134_migration_follows_roster_history_and_adds_source_unique():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0134_aa_makeup_source_identity.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "0134_aa_makeup_source_identity"' in migration
    assert 'down_revision = "0133_aa_roster_history"' in migration
    assert "uk_acad_makeup_source_biz" in migration
    assert "teaching_class_id" in migration
    assert "roster_version_id" in migration
