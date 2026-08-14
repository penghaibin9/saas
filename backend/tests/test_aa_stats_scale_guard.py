"""PR #101 production audit: stats overview aggregates high-volume facts in SQL."""
from __future__ import annotations

import inspect

from app.modules.academic_affairs.services import academic_affairs_stats_scale_guard as guard
from app.modules.academic_affairs.services import academic_affairs_stats_service as legacy


_PATCHED = (
    "_i_registration",
    "_i_teaching_task",
    "_i_grade_publish",
    "_i_fail_rate",
    "_i_graduation",
    "_i_exam",
    "_i_resource",
    "_i_schedule_change",
    "_i_selection",
)


def test_stats_scale_guard_is_installed_on_legacy_overview_globals():
    for name in _PATCHED:
        assert getattr(legacy, name) is getattr(guard, name)
        assert hasattr(legacy, f"_stats_scale_guard_original{name}")


def test_high_volume_stats_use_database_aggregates_not_python_full_column_counts():
    for name in _PATCHED:
        source = inspect.getsource(getattr(guard, name))
        assert "func.count" in source or "func.sum" in source
        assert "db.scalars(q).all()" not in source
        assert "statuses =" not in source
        assert "len(statuses)" not in source


def test_registration_exam_and_teaching_task_term_filters_use_subqueries():
    registration = inspect.getsource(guard._i_registration)
    exam = inspect.getsource(guard._i_exam)
    teaching_task = inspect.getsource(guard._i_teaching_task)

    assert "batch_ids = select(AaRegistrationBatch.id)" in registration
    assert "AaRegistration.batch_id.in_(batch_ids)" in registration
    assert "batch_ids = select(AaExamBatch.id)" in exam
    assert "AaExamCourse.batch_id.in_(batch_ids)" in exam
    assert "batch_ids = select(AaTeachingTaskBatch.id)" in teaching_task
    assert "AaTeachingTaskBatch.term_id == int(term_id)" in teaching_task
    assert "AaTeachingTask.batch_id.in_(batch_ids)" in teaching_task
    assert "AaTeachingTaskBatch.is_deleted.is_(False)" in teaching_task

    for source in (registration, exam, teaching_task):
        assert ").all()]" not in source
