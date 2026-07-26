"""学生考试开始时间必须按学校本地时区判断，不得拿UTC直接比较本地文本。"""
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo


def _course(date="2026-07-26", start="09:00"):
    return SimpleNamespace(exam_date=date, start_time=start)


def test_exam_started_uses_asia_shanghai_local_time():
    from app.modules.academic_affairs.services.student_exam_read_service import exam_started

    zone = ZoneInfo("Asia/Shanghai")
    assert exam_started(_course(), zone=zone,
                        now=datetime(2026, 7, 26, 9, 0, tzinfo=zone)) is True
    assert exam_started(_course(), zone=zone,
                        now=datetime(2026, 7, 26, 8, 59, tzinfo=zone)) is False


def test_exam_started_converts_utc_instant_to_school_timezone():
    from app.modules.academic_affairs.services.student_exam_read_service import exam_started

    school_zone = ZoneInfo("Asia/Shanghai")
    utc = ZoneInfo("UTC")
    # UTC 01:00 == 上海 09:00，应判定已开考。
    assert exam_started(_course(), zone=school_zone,
                        now=datetime(2026, 7, 26, 1, 0, tzinfo=utc)) is True


def test_invalid_exam_date_does_not_crash_student_home():
    from app.modules.academic_affairs.services.student_exam_read_service import exam_started

    zone = ZoneInfo("Asia/Shanghai")
    assert exam_started(_course(date="待定", start="上午"), zone=zone,
                        now=datetime(2026, 7, 26, 9, 0, tzinfo=zone)) is False
