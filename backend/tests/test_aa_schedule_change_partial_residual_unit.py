from types import SimpleNamespace

import pytest


class _FakeDb:
    def __init__(self):
        self.items = []

    def add(self, item):
        item.id = 9000 + len(self.items)
        self.items.append(item)

    def flush(self):
        return None


def _origin(**overrides):
    values = {
        "batch_id": 27,
        "task_id": 5962,
        "course_id": 100,
        "course_name": "软件测试技术",
        "class_id": 2103,
        "class_name": "软件技术2501班",
        "teacher_key": "sbx_t0257",
        "teacher_name": "何晨曦",
        "weekday": 1,
        "slot_no": 1,
        "start_week": 1,
        "end_week": 18,
        "week_parity": "ALL",
        "classroom_id": 10,
        "classroom_text": "教学楼101",
        "source": "AUTO",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_partial_adjust_creates_two_unlinked_residual_segments():
    from app.core.context import set_tenant
    from app.modules.academic_affairs.services.academic_affairs_schedule_change_service import (
        _create_adjust_residuals,
    )

    set_tenant({"tenantId": "1000000000000000007"})
    db = _FakeDb()
    change = SimpleNamespace(
        id=7, change_type="ADJUST", target_start_week=3,
        target_end_week=3, target_week_parity="ALL",
    )

    ids = _create_adjust_residuals(db, change, _origin())

    assert ids == [9000, 9001]
    assert [(item.start_week, item.end_week) for item in db.items] == [(1, 2), (4, 18)]
    assert all(item.change_id is None for item in db.items)
    assert all(item.status == "EFFECTIVE" for item in db.items)


def test_adjust_window_cannot_move_weeks_outside_origin():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services.academic_affairs_schedule_change_service import (
        _validate_adjust_window,
    )

    with pytest.raises(AppException):
        _validate_adjust_window(_origin(), 0, 3, "ALL")
    with pytest.raises(AppException):
        _validate_adjust_window(_origin(week_parity="ODD"), 1, 3, "EVEN")
