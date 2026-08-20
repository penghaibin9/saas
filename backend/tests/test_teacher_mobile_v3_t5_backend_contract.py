from __future__ import annotations

import inspect

from app.modules.internship.services import internship_service


def test_t5_attendance_exception_command_is_atomic_single_object_and_conflict_guarded():
    source = inspect.getsource(internship_service.handle_attendance_exception)
    assert "versioned_update" in source
    assert "expected_version" in source
    assert 'if c.status == "COMPLETED"' in source
    assert 'AppException("DATA_CONFLICT"' in source
    assert 'extra_where=(AttendanceException.status != "COMPLETED",)' in source
    assert "_rec_in_scope(_current_scope(user)" in source
    assert "for exception_id in" not in source
    assert "exception_ids" not in source


def test_t5_attendance_exception_action_set_stays_canonical():
    source = inspect.getsource(internship_service.handle_attendance_exception)
    assert '("REASONABLE", "ABNORMAL", "TO_RISK")' in source
    assert 'action == "TO_RISK"' in source
    assert 'todo_done(db, biz_id=c.id' in source
