from __future__ import annotations

import inspect
from collections import Counter
from types import SimpleNamespace

from app.modules.academic_affairs.services import academic_affairs_schedule_conflict_index as conflict_index
from app.modules.academic_affairs.services import academic_affairs_scheduling_final_service as scheduling_service


def _item(item_id: int, weekday: int, slot_no: int):
    return SimpleNamespace(id=item_id, weekday=weekday, slot_no=slot_no)


def _legacy_same_slot_pairs(items):
    pairs = []
    for left_index, left in enumerate(items):
        for right in items[left_index + 1 :]:
            if left.weekday == right.weekday and left.slot_no == right.slot_no:
                pairs.append((left.id, right.id))
    return pairs


def test_conflict_index_preserves_legacy_candidate_pair_order():
    items = [
        _item(1, 1, 1),
        _item(2, 2, 1),
        _item(3, 1, 1),
        _item(4, 1, 2),
        _item(5, 1, 1),
        _item(6, 2, 1),
    ]

    actual = [(left.id, right.id) for left, right in conflict_index.iter_same_slot_pairs(items)]
    assert actual == _legacy_same_slot_pairs(items)
    assert actual == [(1, 3), (1, 5), (2, 6), (3, 5)]


def test_conflict_index_1000_schedule_items_avoids_global_quadratic_pair_scan():
    # V4 生产量级门禁：至少 1000 ScheduleItem。均匀落到 7*10 个真实课位后，
    # 候选比较量只能等于各槽位内部组合数，不能退化回全局 499,500 对。
    items = [
        _item(index + 1, index % 7 + 1, index % 10 + 1)
        for index in range(1000)
    ]
    actual = list(conflict_index.iter_same_slot_pairs(items))

    counts = Counter((item.weekday, item.slot_no) for item in items)
    expected_pairs = sum(size * (size - 1) // 2 for size in counts.values())
    global_pairs = len(items) * (len(items) - 1) // 2

    assert len(actual) == expected_pairs
    assert len(actual) < global_pairs // 20


def test_conflict_report_consumes_slot_index_instead_of_global_suffix_scan():
    source = inspect.getsource(scheduling_service.conflict_report_in_session)
    assert "conflict_index.iter_same_slot_pairs(items)" in source
    assert "items[left_index + 1:]" not in source
