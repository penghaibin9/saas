"""教学任务周次与应开学期必须读取学期/校历，禁止固定18周或全方案一次生成。"""
from datetime import datetime
from types import SimpleNamespace

import pytest


class _Query:
    def __init__(self, *, first=None, rows=None):
        self._first = first
        self._rows = list(rows or [])

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._first

    def all(self):
        return list(self._rows)


class _Db:
    def __init__(self, term, events=None):
        self.term = term
        self.events = list(events or [])

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "AaTerm":
            return _Query(first=self.term)
        if name == "AaCalendarEvent":
            return _Query(rows=self.events)
        raise AssertionError(f"unexpected model {name}")


def _term(**overrides):
    data = {
        "id": 1, "tenant_id": 1, "year_code": "2026-2027", "term_no": 1,
        "teaching_weeks": None, "exam_week_start": None,
        "start_date": None, "end_date": None, "is_deleted": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _service():
    from app.modules.academic_affairs.services import academic_affairs_task_generation_service as service
    return service


def test_explicit_teaching_weeks_has_highest_priority(monkeypatch):
    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: 1)
    assert service.resolve_teaching_weeks(_Db(_term(teaching_weeks=16, exam_week_start=18)), 1) == (
        16, "TERM_TEACHING_WEEKS"
    )


def test_exam_week_start_derives_teaching_weeks(monkeypatch):
    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: 1)
    assert service.resolve_teaching_weeks(_Db(_term(exam_week_start=17)), 1) == (
        16, "TERM_EXAM_WEEK_START"
    )


def test_calendar_teaching_events_are_used_before_term_date_range(monkeypatch):
    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: 1)
    term = _term(start_date=datetime(2026, 2, 23), end_date=datetime(2026, 7, 12))
    event = SimpleNamespace(start_date=datetime(2026, 2, 23), end_date=datetime(2026, 6, 14))
    assert service.resolve_teaching_weeks(_Db(term, [event]), 1) == (
        16, "CALENDAR_TEACHING_EVENTS"
    )


def test_term_date_range_is_compatible_fallback(monkeypatch):
    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: 1)
    assert service.resolve_teaching_weeks(_Db(_term(
        start_date=datetime(2026, 2, 23), end_date=datetime(2026, 6, 28),
    )), 1) == (18, "TERM_DATE_RANGE")


def test_legacy_18_is_explicit_last_resort(monkeypatch, caplog):
    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: 1)
    assert service.resolve_teaching_weeks(_Db(_term()), 1) == (18, "LEGACY_FALLBACK_18")
    assert "no reliable teaching-week configuration" in caplog.text


def test_missing_term_is_rejected(monkeypatch):
    from app.core.exceptions import AppException

    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: 1)
    with pytest.raises(AppException):
        service.resolve_teaching_weeks(_Db(None), 999)


def test_class_semester_is_derived_from_academic_year_and_admission_grade():
    service = _service()
    school_class = SimpleNamespace(grade="2024")
    assert service.resolve_class_semester(_term(year_code="2026-2027", term_no=1), school_class) == 5
    assert service.resolve_class_semester(_term(year_code="2026-2027", term_no=2), school_class) == 6


def test_class_semester_accepts_grade_label_but_not_ambiguous_data():
    service = _service()
    assert service.resolve_class_semester(
        _term(year_code="2025-2026", term_no=2), SimpleNamespace(grade="2024级")
    ) == 4
    assert service.resolve_class_semester(
        _term(year_code="未知", term_no=2), SimpleNamespace(grade="2024级")
    ) is None
    assert service.resolve_class_semester(
        _term(year_code="2025-2026", term_no=3), SimpleNamespace(grade="2024级")
    ) is None


def test_future_class_is_not_guessed_into_current_term():
    service = _service()
    assert service.resolve_class_semester(
        _term(year_code="2025-2026", term_no=1), SimpleNamespace(grade="2026")
    ) is None


def test_public_task_service_uses_explicit_generator_without_facade():
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    assert service.generation.resolve_teaching_weeks.__module__.endswith(
        "academic_affairs_task_generation_service"
    )
    assert "facade" not in service.generate_batch.__module__
