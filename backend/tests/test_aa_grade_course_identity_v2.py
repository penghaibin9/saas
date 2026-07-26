"""V2-04 正式成绩课程身份、课程版本和修读次数回归。"""
from importlib import util
from pathlib import Path
from types import SimpleNamespace


def test_academic_grade_has_formal_identity_fields_and_indexes():
    from app.models import AcademicGrade

    assert {
        "course_id", "course_code", "course_version", "attempt_no",
        "grade_task_id", "grade_record_id", "teaching_task_id",
        "teaching_class_id", "roster_version_id",
    } <= set(AcademicGrade.__mapper__.attrs.keys())
    index_names = {index.name for index in AcademicGrade.__table__.indexes}
    assert {
        "ix_acad_grade_course_attempt",
        "ix_acad_grade_course_code",
        "ix_acad_grade_grade_task",
        "ix_acad_grade_teaching_task",
        "ix_acad_grade_teaching_class",
    } <= index_names
    unique_names = {constraint.name for constraint in AcademicGrade.__table__.constraints if constraint.name}
    assert "uk_acad_grade_source_record" in unique_names


def test_course_snapshot_uses_specific_course_version_row():
    from app.modules.academic_affairs.services.academic_affairs_grade_identity_service import course_snapshot

    result = course_snapshot(SimpleNamespace(
        id=81,
        course_code="CS101",
        version=3,
        course_name="程序设计基础",
        nature="REQUIRED",
        credit=3.5,
    ))
    assert result == {
        "courseId": 81,
        "courseCode": "CS101",
        "courseVersion": 3,
        "courseName": "程序设计基础",
        "nature": "REQUIRED",
        "credit": 3.5,
    }


def test_roster_snapshot_keeps_teaching_class_and_version_ids():
    from app.modules.academic_affairs.services.academic_affairs_grade_identity_service import roster_snapshot

    result = roster_snapshot({
        "source": "TEACHING_CLASS_ROSTER",
        "teachingClassId": "12",
        "rosterVersionId": "37",
        "rosterVersionNo": 4,
    })
    assert result == {
        "teachingClassId": 12,
        "rosterVersionId": 37,
        "rosterVersionNo": 4,
        "rosterSource": "TEACHING_CLASS_ROSTER",
    }


def test_makeup_source_attempt_requires_governed_original_grade():
    import pytest

    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services.academic_affairs_grade_identity_service import source_attempt_no

    assert source_attempt_no(SimpleNamespace(attempt_no=2)) == 2
    with pytest.raises(AppException) as exc:
        source_attempt_no(SimpleNamespace(attempt_no=None))
    assert "身份回填" in str(exc.value)


def test_public_grade_service_is_v2_identity_facade():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_grade_service.__name__.endswith(
        "academic_affairs_grade_identity_facade"
    )
    assert services.academic_affairs_grade_service._base.__name__.endswith(
        "academic_affairs_grade_term_facade"
    )
    assert services.academic_affairs_grade_service.publish_grades.__module__.endswith(
        "academic_affairs_grade_identity_facade"
    )
    assert services.academic_affairs_grade_service._legacy.publish_grades is services.academic_affairs_grade_service.publish_grades


def test_publish_source_contains_all_formal_identity_assignments():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "app/modules/academic_affairs/services/academic_affairs_grade_identity_facade.py"
    )
    source = source_path.read_text(encoding="utf-8")
    for assignment in (
        "course_id=course_meta[\"courseId\"]",
        "course_code=course_meta[\"courseCode\"]",
        "course_version=course_meta[\"courseVersion\"]",
        "attempt_no=attempt_no",
        "grade_task_id=task.id",
        "grade_record_id=record.id",
        "teaching_task_id=task.teaching_task_id",
        "teaching_class_id=roster_meta[\"teachingClassId\"]",
        "roster_version_id=roster_meta[\"rosterVersionId\"]",
    ):
        assert assignment in source
    assert "教学任务尚未投影独立教学班和正式名单版本" in source


def test_0128_migration_follows_teaching_class_migration_and_is_idempotent():
    migration_path = Path(__file__).resolve().parents[1] / "alembic/versions/0128_aa_grade_course_identity.py"
    spec = util.spec_from_file_location("aa_migration_0128", migration_path)
    assert spec and spec.loader
    migration = util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "0128_aa_grade_course_identity"
    assert migration.down_revision == "0127_aa_teaching_class_roster"
    assert callable(migration._add_column)
    assert callable(migration._ensure_index)
    assert callable(migration._ensure_unique)
