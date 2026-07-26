"""学生课表只能合并同一发布批次，并按课表事实去重。"""


def _item(item_id, *, source="CLASS_DERIVED", weekday=1, slot=1, course="高等数学"):
    return {
        "itemId": item_id,
        "source": source,
        "weekday": weekday,
        "slotNo": slot,
        "startWeek": 1,
        "endWeek": 16,
        "weekParity": "ALL",
        "courseName": course,
        "teacherKey": "T001",
        "classroom": "A101",
    }


def test_same_item_from_class_and_selection_is_returned_once():
    from app.modules.academic_affairs.services.academic_affairs_schedule_facade import (
        merge_student_schedule_items,
    )

    rows = merge_student_schedule_items(
        [_item("10", source="CLASS_DERIVED")],
        [_item("10", source="ENROLLED")],
    )

    assert len(rows) == 1
    assert rows[0]["source"] == "ENROLLED"


def test_different_items_are_kept_and_sorted():
    from app.modules.academic_affairs.services.academic_affairs_schedule_facade import (
        merge_student_schedule_items,
    )

    rows = merge_student_schedule_items(
        [_item("20", weekday=2, slot=1, course="英语")],
        [_item("10", weekday=1, slot=3, course="数学")],
    )

    assert [row["itemId"] for row in rows] == ["10", "20"]


def test_legacy_rows_without_item_id_use_schedule_fact_key():
    from app.modules.academic_affairs.services.academic_affairs_schedule_facade import (
        merge_student_schedule_items,
    )

    first = _item("", source="CLASS_DERIVED")
    duplicate = _item("", source="ENROLLED")
    other = _item("", source="ENROLLED", slot=2)

    rows = merge_student_schedule_items([first], [duplicate, other])

    assert len(rows) == 2
    assert rows[0]["source"] == "ENROLLED"
    assert rows[1]["slotNo"] == 2


def test_public_schedule_service_points_to_batch_safe_facade():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_schedule_service.student_view.__module__.endswith(
        "academic_affairs_schedule_facade"
    )
