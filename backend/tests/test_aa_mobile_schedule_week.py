"""师生四端课表必须共用确定的当前学期周次和学校作息。"""
from datetime import date, datetime
from pathlib import Path


def test_before_term_start_is_week_zero():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        teaching_week_from_dates,
    )

    assert teaching_week_from_dates(date(2026, 9, 1), date(2026, 8, 31)) == 0


def test_term_start_day_is_week_one():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        teaching_week_from_dates,
    )

    assert teaching_week_from_dates(date(2026, 9, 1), date(2026, 9, 1)) == 1


def test_week_changes_every_seven_days():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        teaching_week_from_dates,
    )

    start = date(2026, 9, 1)
    assert teaching_week_from_dates(start, date(2026, 9, 7)) == 1
    assert teaching_week_from_dates(start, date(2026, 9, 8)) == 2
    assert teaching_week_from_dates(start, date(2026, 9, 15)) == 3


def test_datetime_and_date_inputs_share_same_rule():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        teaching_week_from_dates,
    )

    assert teaching_week_from_dates(
        datetime(2026, 9, 1, 8, 0),
        datetime(2026, 9, 9, 23, 59),
    ) == 2


def test_missing_dates_are_unknown_not_week_one():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        teaching_week_from_dates,
    )

    assert teaching_week_from_dates(None, date(2026, 9, 1)) is None
    assert teaching_week_from_dates(date(2026, 9, 1), None) is None


def test_schedule_time_band_resolver_prefers_effective_band_and_keeps_campus_variants():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        resolve_schedule_time_bands,
    )

    slots = [{
        "id": 1,
        "slot_no": 1,
        "slot_name": "第一节",
        "start_time": "08:00",
        "end_time": "08:45",
        "enabled": True,
    }]
    bands = [
        {
            "id": 10,
            "slot_id": 1,
            "campus_code": "MAIN",
            "start_time": "08:10",
            "end_time": "08:55",
            "effective_start": date(2026, 9, 1),
            "effective_end": date(2027, 1, 31),
            "status": "ENABLED",
        },
        {
            "id": 11,
            "slot_id": 1,
            "campus_code": "EAST",
            "start_time": "08:20",
            "end_time": "09:05",
            "effective_start": date(2026, 9, 1),
            "effective_end": date(2027, 1, 31),
            "status": "ENABLED",
        },
    ]

    result = resolve_schedule_time_bands(slots, bands, date(2026, 10, 1))
    assert [(item["campusCode"], item["startTime"], item["endTime"]) for item in result] == [
        ("EAST", "08:20", "09:05"),
        ("MAIN", "08:10", "08:55"),
    ]


def test_teacher_schedule_page_uses_backend_time_bands_without_inventing_one_campus_time():
    root = Path(__file__).resolve().parents[2]
    page = (
        root / "miniapp/src/pages/teacher/my-schedule/index.vue"
    ).read_text(encoding="utf-8")

    assert "this.timeBands = (data && data.timeBands) || []" in page
    assert "Number(band.slotNo) === Number(item.slotNo)" in page
    assert "if (ranges.length > 1) return '按校区作息'" in page
    assert "节次时间来自学校作息" in page
    assert "this.timeBands = []" in page
