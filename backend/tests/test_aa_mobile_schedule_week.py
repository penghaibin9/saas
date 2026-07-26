"""师生四端课表必须共用确定的当前学期周次。"""
from datetime import date, datetime


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
