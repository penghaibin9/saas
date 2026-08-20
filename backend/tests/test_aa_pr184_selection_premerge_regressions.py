"""PR #184 pre-merge regressions discovered by integrated Gold review."""
from __future__ import annotations

import importlib
import inspect

from app.modules.academic_affairs.routers import academic_selection_final_router


selection_base = importlib.import_module(
    "app.modules.academic_affairs.services.academic_affairs_selection_service"
)
selection_read = importlib.import_module(
    "app.modules.academic_affairs.services.academic_affairs_selection_read_service"
)
selection_course_command = importlib.import_module(
    "app.modules.academic_affairs.services.academic_affairs_selection_course_command_service"
)


def test_selection_projection_and_preflight_do_not_take_term_write_lock():
    assert selection_base._TERM_GUARD_READ_ONLY.get() is False
    with selection_base.selection_readonly_term_guard():
        assert selection_base._TERM_GUARD_READ_ONLY.get() is True
    assert selection_base._TERM_GUARD_READ_ONLY.get() is False

    guard_source = inspect.getsource(selection_base._require_term_reference_writable)
    assert "_TERM_GUARD_READ_ONLY.get()" in guard_source
    assert "stmt = stmt.with_for_update()" in guard_source

    read_source = inspect.getsource(selection_read.student_courses)
    assert "with _final.selection_readonly_term_guard():" in read_source

    batch_preflight_source = inspect.getsource(
        academic_selection_final_router.sel_batch_preflight
    )
    student_preflight_source = inspect.getsource(
        academic_selection_final_router.sel_student_preflight
    )
    assert "with selection_final.selection_readonly_term_guard():" in batch_preflight_source
    assert "with selection_final.selection_readonly_term_guard():" in student_preflight_source


def test_selection_supply_create_rejects_min_capacity_above_capacity_before_insert():
    source = inspect.getsource(selection_course_command.add_course)
    validation = 'raise AppException("VALIDATION_ERROR", "开班下限不可大于课程容量")'
    assert validation in source
    assert source.index(validation) < source.index("row = AaSelectionCourse(")
    assert "capacity=capacity" in source
    assert "min_capacity=min_capacity" in source
