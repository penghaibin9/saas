"""D6：LOCKED 后人工调整必须沿 Selection Final → TeachingRoster 唯一真链。"""
from __future__ import annotations

import inspect

from app.modules.academic_affairs.services import academic_affairs_selection_service as selection


def test_locked_adjustment_is_owned_by_selection_final_and_reprojects_roster():
    assert selection.__name__.endswith("academic_affairs_selection_final_service")
    assert selection.adjust_record.__module__.endswith("academic_affairs_selection_final_service")

    source = inspect.getsource(selection.adjust_record)
    consumer = "consumer_counts(db, teaching_task_id=int(course.teaching_task_id))"
    mutate = "record.status = _base._REC_DROPPED"
    flush = "db.flush()"
    project = "roster_projection.project_selection_course_locked("
    commit = "db.commit()"

    assert "AaSelectionRecord(" not in source
    assert "db.add(AaSelectionRecord" not in source
    assert "with_for_update().first()" in source
    assert "batch.status != _base._BATCH_LOCKED" in source
    assert consumer in source
    assert 'counts.get("TOTAL")' in source
    assert "已冻结考勤、考务或成绩名单" in source
    assert mutate in source
    assert "AaSelectionCourse.selected_count - 1" in source
    assert flush in source
    assert project in source
    assert '"SELECTION_RECORD_ADJUST"' in source
    assert commit in source
    assert source.index(consumer) < source.index(mutate)
    assert source.index(mutate) < source.index(flush) < source.index(project) < source.index(commit)
