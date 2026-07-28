"""教务成绩身份字段通过独立扩展注册，不修改当前 main 的旧学业模型文件。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SOURCE = (ROOT / "app/models/academic.py").read_text(encoding="utf-8")
REGISTRY_SOURCE = (ROOT / "app/models/academic_affairs_registry.py").read_text(encoding="utf-8")


def test_shared_legacy_model_contains_only_current_main_columns():
    assert "UniqueConstraint" not in LEGACY_SOURCE
    assert "grade_record_id" not in LEGACY_SOURCE
    assert "source_biz_type" not in LEGACY_SOURCE
    assert "roster_version_id" not in LEGACY_SOURCE
    assert "student_id: Mapped[int | None]" in LEGACY_SOURCE
    assert "batch_id: Mapped[int | None]" in LEGACY_SOURCE
    assert "apply_id: Mapped[int | None]" in LEGACY_SOURCE


def test_extension_registry_installs_grade_and_makeup_identity_columns():
    import app.models  # noqa: F401
    from app.models import AcademicGrade, AcademicMakeup

    for column in (
        "course_id",
        "course_code",
        "course_version",
        "attempt_no",
        "grade_task_id",
        "grade_record_id",
        "source_biz_type",
        "source_biz_id",
        "teaching_task_id",
        "teaching_class_id",
        "roster_version_id",
    ):
        assert column in AcademicGrade.__table__.c
        assert hasattr(AcademicGrade, column)

    for column in (
        "origin_grade_id",
        "source_biz_type",
        "source_biz_id",
        "course_id",
        "course_code",
        "course_version",
        "attempt_no",
        "teaching_task_id",
        "teaching_class_id",
        "roster_version_id",
    ):
        assert column in AcademicMakeup.__table__.c
        assert hasattr(AcademicMakeup, column)


def test_extension_indexes_and_unique_constraints_are_registered_once():
    import app.models  # noqa: F401
    from app.models import AcademicGrade, AcademicMakeup

    grade_indexes = {index.name for index in AcademicGrade.__table__.indexes}
    makeup_indexes = {index.name for index in AcademicMakeup.__table__.indexes}
    grade_constraints = {constraint.name for constraint in AcademicGrade.__table__.constraints}
    makeup_constraints = {constraint.name for constraint in AcademicMakeup.__table__.constraints}

    assert "ix_acad_grade_course_attempt" in grade_indexes
    assert "ix_acad_grade_source_biz" in grade_indexes
    assert "uk_acad_grade_source_record" in grade_constraints
    assert "uk_acad_grade_source_biz" in grade_constraints
    assert "ix_acad_makeup_course_attempt" in makeup_indexes
    assert "ix_acad_makeup_roster_version" in makeup_indexes
    assert "uk_acad_makeup_source_biz" in makeup_constraints


def test_registry_explicitly_loads_the_extension_module():
    assert "academic_grade_extensions" in REGISTRY_SOURCE
    assert "install_academic_grade_extensions()" in REGISTRY_SOURCE
