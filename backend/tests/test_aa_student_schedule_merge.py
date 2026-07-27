"""学生课表只能合并同一发布批次，并按课表事实去重。"""
from datetime import date, datetime
from types import SimpleNamespace


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


def _slot(slot_id=1, slot_no=1, start="08:00", end="08:45"):
    return SimpleNamespace(
        id=slot_id,
        slot_no=slot_no,
        slot_name=f"第{slot_no}节",
        start_time=start,
        end_time=end,
        campus_code=None,
        enabled=True,
        status="ENABLED",
    )


def _band(
    band_id=1,
    *,
    slot_id=1,
    campus="MAIN",
    start="08:10",
    end="08:55",
    effective_start=datetime(2026, 5, 1),
    effective_end=datetime(2026, 9, 30),
    status="ENABLED",
):
    return SimpleNamespace(
        id=band_id,
        slot_id=slot_id,
        band_name="夏令作息",
        campus_code=campus,
        start_time=start,
        end_time=end,
        effective_start=effective_start,
        effective_end=effective_end,
        status=status,
    )


def test_effective_time_band_overrides_base_slot_time():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        resolve_schedule_time_bands,
    )

    rows = resolve_schedule_time_bands([_slot()], [_band()], date(2026, 7, 1))

    assert rows == [{
        "slotNo": 1,
        "slotName": "第1节",
        "startTime": "08:10",
        "endTime": "08:55",
        "bandName": "夏令作息",
        "campusCode": "MAIN",
        "source": "TIME_BAND",
    }]


def test_expired_time_band_falls_back_to_base_slot_time():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        resolve_schedule_time_bands,
    )

    rows = resolve_schedule_time_bands([_slot()], [_band()], date(2026, 12, 1))

    assert rows[0]["startTime"] == "08:00"
    assert rows[0]["endTime"] == "08:45"
    assert rows[0]["source"] == "TIME_SLOT"


def test_multiple_campus_time_bands_are_retained_without_guessing():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        resolve_schedule_time_bands,
    )

    rows = resolve_schedule_time_bands(
        [_slot()],
        [_band(1, campus="MAIN"), _band(2, campus="EAST", start="08:30", end="09:15")],
        date(2026, 7, 1),
    )

    assert {row["campusCode"] for row in rows} == {"MAIN", "EAST"}
    assert {row["startTime"] for row in rows} == {"08:10", "08:30"}


def test_student_pc_schedule_consumes_backend_time_band_contract():
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "student-portal/src/views/academic/StudentScheduleView.vue"
    text = path.read_text(encoding="utf-8")

    assert "schedule.value.timeBands" in text
    assert "function slotLabel" in text
    assert "按校区作息" in text
    assert "第${item.slotNo}节" not in text
