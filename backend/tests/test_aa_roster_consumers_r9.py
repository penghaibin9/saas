"""R9 选课、考勤、考务、成绩统一名单版本回归。"""
from pathlib import Path


def test_roster_consumer_model_has_stable_identity_fields():
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    fields = set(AaRosterConsumerSnapshot.__mapper__.attrs.keys())
    assert {
        "consumer_type", "consumer_id", "teaching_task_id", "teaching_class_id",
        "roster_version_id", "roster_version_no", "roster_source", "roster_hash",
        "member_count", "student_ids_json", "captured_at", "status",
    } <= fields
    unique_names = {
        constraint.name for constraint in AaRosterConsumerSnapshot.__table__.constraints
        if constraint.name
    }
    assert "uk_aa_roster_consumer" in unique_names


def test_roster_hash_is_order_independent_and_zero_safe():
    from app.modules.academic_affairs.services.academic_affairs_roster_consumer_service import roster_hash

    assert roster_hash([3, 1, 2, 2]) == roster_hash([1, 2, 3])
    assert roster_hash([]) == roster_hash(set())
    assert roster_hash([]) != roster_hash([1])


def test_r9_migration_follows_grade_identity_and_never_guesses_history():
    root = Path(__file__).resolve().parents[1]
    migration = (
        root / "alembic/versions/0129_aa_roster_consumer_snapshot.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "0129_aa_roster_consumer_snapshot"' in migration
    assert 'down_revision = "0128_aa_grade_course_identity"' in migration
    assert "t_aa_roster_consumer_snapshot" in migration
    assert "禁止迁移时按课程名或行政班猜测" in migration
    for column in (
        "consumer_type", "consumer_id", "teaching_task_id", "teaching_class_id",
        "roster_version_id", "roster_hash", "student_ids_json",
    ):
        assert column in migration


def test_attendance_exam_and_grade_freeze_at_governed_nodes():
    root = Path(__file__).resolve().parents[1]
    attendance = (
        root / "app/modules/academic_affairs/services/academic_affairs_attendance_roster_identity_facade.py"
    ).read_text(encoding="utf-8")
    exam = (
        root / "app/modules/academic_affairs/services/academic_affairs_exam_roster_identity_facade.py"
    ).read_text(encoding="utf-8")
    grade = (
        root / "app/modules/academic_affairs/services/academic_affairs_grade_term_facade.py"
    ).read_text(encoding="utf-8")

    assert '"ATTENDANCE_SESSION"' in attendance
    assert "freeze_consumer_snapshot" in attendance
    assert attendance.index("db.flush()") < attendance.index("freeze_consumer_snapshot") < attendance.index("db.commit()")

    assert '"EXAM_COURSE"' in exam
    assert "resolve_versioned_roster" in exam
    assert "require_consumer_snapshot_current" in exam
    assert "_original_assign_seats" in exam
    assert "_original_list_courses" in exam

    assert '"GRADE_TASK"' in grade
    assert grade.index("freeze_consumer_snapshot") < grade.index("AaGradeTask.status: \"SUBMITTED\"")
    assert "rosterVersionId" in grade


def test_grade_publish_requires_frozen_roster_still_current():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_grade_roster_identity_guard.py"
    ).read_text(encoding="utf-8")

    assert "require_consumer_snapshot_current" in source
    assert '"GRADE_TASK"' in source
    assert source.index("require_consumer_snapshot_current") < source.index("_original_publish(task_id, user)")


def test_public_facade_names_stay_compatible_while_r9_patches_are_active():
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import (
        academic_affairs_attendance_facade as attendance,
        academic_affairs_exam_facade as exam,
        academic_affairs_grade_identity_facade as grade,
    )

    assert services.academic_affairs_attendance_service.__name__.endswith("academic_affairs_attendance_facade")
    assert attendance.create_session.__module__.endswith("academic_affairs_attendance_roster_identity_facade")
    assert services.academic_affairs_exam_service.__name__.endswith("academic_affairs_exam_term_facade")
    assert exam.confirm_course.__module__.endswith("academic_affairs_exam_roster_identity_facade")
    assert exam.assign_seats.__module__.endswith("academic_affairs_exam_roster_identity_facade")
    assert services.academic_affairs_grade_service.__name__.endswith("academic_affairs_grade_identity_facade")
    assert grade.publish_grades.__module__.endswith("academic_affairs_grade_roster_identity_guard")


def test_consumer_service_rejects_silent_roster_switch():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_roster_consumer_service.py"
    ).read_text(encoding="utf-8")

    assert "禁止静默换版" in source
    assert "正式名单已换版" in source
    assert "APPROVAL_VERSION_CONFLICT" in source
    assert "consumer_counts" in source
