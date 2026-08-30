"""Student survival path: choose with context, then consume today's formal timetable."""


def _item(*, weekday=1, slot=1, start=1, end=18, parity="ALL", name="语文"):
    return {
        "itemId": f"{weekday}-{slot}-{name}",
        "weekday": weekday,
        "slotNo": slot,
        "startWeek": start,
        "endWeek": end,
        "weekParity": parity,
        "courseName": name,
    }


def test_today_projection_honours_weekday_week_range_and_parity():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        project_student_today_items,
    )

    context = {
        "todayDate": "2026-08-31",
        "todayWeek": 3,
        "todayWeekday": 1,
        "calendarSource": "NORMAL",
    }
    rows = project_student_today_items([
        _item(weekday=1, slot=3, parity="ODD", name="数学"),
        _item(weekday=1, slot=1, parity="ALL", name="语文"),
        _item(weekday=1, slot=2, parity="EVEN", name="英语"),
        _item(weekday=2, slot=1, name="体育"),
        _item(weekday=1, slot=4, start=4, name="美术"),
    ], context)

    assert [row["courseName"] for row in rows] == ["语文", "数学"]
    assert all(row["sessionDate"] == "2026-08-31" for row in rows)
    assert all(row["weekNo"] == 3 for row in rows)


def test_today_projection_respects_no_class_calendar_days():
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import (
        project_student_today_items,
    )

    for source in ("HOLIDAY", "SWAP_SOURCE", "OUT_OF_TERM"):
        assert project_student_today_items(
            [_item()],
            {"todayWeek": 1, "todayWeekday": 1, "calendarSource": source},
        ) == []


def test_selection_projection_exposes_published_meeting_context():
    from pathlib import Path

    service = Path(__file__).resolve().parents[1] / (
        "app/modules/academic_affairs/services/academic_affairs_selection_final_service.py"
    )
    source = service.read_text(encoding="utf-8")

    assert "def _student_course_schedule_projection" in source
    assert '"scheduleItems"' in source
    assert 'AaScheduleBatch.status == "PUBLISHED"' in source
    assert 'AaScheduleItem.status == "EFFECTIVE"' in source
