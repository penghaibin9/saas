from pathlib import Path

path = Path("backend/tests/test_aa_attendance_class_options_formal_schedule.py")
text = path.read_text(encoding="utf-8")
marker = "test_attendance_class_options_excludes_non_executable_task_even_with_formal_schedule"
if marker in text:
    raise SystemExit("task-readiness contract already exists")
text += r'''


def test_attendance_class_options_excludes_non_executable_task_even_with_formal_schedule(db_mode):
    from app.modules.academic_affairs.services import mobile_academic_affairs_facade as facade

    _ctx()
    db = _session()
    _term, task_ready, _task_old, _active_batch, _ready_item = _seed(db)
    task_ready.status = "ASSIGNED"
    db.commit()
    task_id = str(task_ready.id)
    db.close()

    result = facade.teacher_attendance_class_options(_user())
    assert task_id not in {item["teachingTaskId"] for item in result["items"]}


def test_attendance_class_options_reuses_canonical_task_execution_guard():
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as attendance
    from app.modules.academic_affairs.services import mobile_academic_affairs_facade as facade

    assert attendance.attendance_task_executable("TEACHER_CONFIRMED") is True
    assert attendance.attendance_task_executable("COLLEGE_REVIEW") is True
    assert attendance.attendance_task_executable("APPROVED") is True
    assert attendance.attendance_task_executable("READY") is True
    assert attendance.attendance_task_executable("ASSIGNED") is False
    assert attendance.attendance_task_executable("PENDING_ASSIGN") is False

    source = inspect.getsource(facade.teacher_attendance_class_options)
    assert "attendance_task_executable" in source
    assert 'status.notin_(["PENDING_ASSIGN", "REJECTED_BY_TEACHER", "MERGED"])' not in source
'''
path.write_text(text, encoding="utf-8")
