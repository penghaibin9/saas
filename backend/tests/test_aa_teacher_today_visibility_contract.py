import inspect


def test_current_formal_schedule_visibility_is_not_hidden_by_attendance_task_state():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today

    source = inspect.getsource(today._teacher_schedule_in_session)
    assert "AaTeachingTask.status.in_" not in source
    assert "attendance_task_executable(task.status)" in source
    assert '"attendanceExecutable": executable' in source
    assert '"attendanceBlockReason": "" if executable else' in source


def test_only_executable_today_occurrence_gets_attendance_deep_link():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today

    source = inspect.getsource(today.teacher_today_projection)
    assert 'attendance_route = None' in source
    assert 'if row.get("attendanceExecutable")' in source
    assert '"attendanceRoute": attendance_route' in source
