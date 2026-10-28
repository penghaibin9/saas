"""Pure regression checks for canonical report counts and period allocation."""
from collections import defaultdict
from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.internship.services import internship_process_statistics_service as process
from app.modules.internship.services import internship_report_quality_service as quality


@pytest.mark.parametrize("required, expected", [(None, 0), (0, 0), (1, 1), (12, 12)])
def test_counts_do_not_infer_tasks_from_frequency_or_dates(required, expected):
    batch = SimpleNamespace(rules_config={"weeklyReport": {
        "frequency": "WEEKLY", "requiredCount": required,
    }})
    assert quality.required_report_counts(batch)["weeklyRequiredCount"] == expected
    assert quality.required_report_counts(batch)["monthlyRequiredCount"] == 0
    assert quality.required_report_counts(batch)["summaryRequiredCount"] == 1
    batch.rules_config["processReport"] = {"summaryRequiredCount": 0}
    assert quality.required_report_counts(batch)["summaryRequiredCount"] == 0


def test_week_and_month_obligations_keep_due_date_windows():
    cfg = {"frequency": "BIWEEKLY", "deadlineWeekday": 7, "requiredCount": 2}
    dues = process._weekly_due_dates(date(2026, 9, 1), date(2026, 12, 30), cfg)
    assert dues == [date(2026, 9, 6), date(2026, 9, 20)]
    _, start, end = process._window("WEEK", "2026-09-14")
    assert [due for due in dues if process._selected_due(due, start, end)] == [date(2026, 9, 20)]
    month_dues = process._month_due_dates(date(2026, 9, 1), date(2026, 12, 30), 2)
    assert month_dues == [date(2026, 9, 30), date(2026, 10, 31)]
    _, start, end = process._window("MONTH", "2026-10-01")
    assert [due for due in month_dues if process._selected_due(due, start, end)] == [date(2026, 10, 31)]


def test_mid_month_end_assigns_required_and_submitted_monthly_report_to_same_week():
    end = date(2026, 9, 15)
    required_due = process._month_due_dates(date(2026, 9, 1), end, 1)[0]
    submitted_due = process._month_due_date(2026, 9, end)
    assert required_due == submitted_due == end
    for anchor, selected in [('2026-09-14', True), ('2026-09-28', False)]:
        _, start, finish = process._window('WEEK', anchor)
        assert process._selected_due(required_due, start, finish) == selected
        assert process._selected_due(submitted_due, start, finish) == selected
    assert process._month_due_date(2026, 8, end) == date(2026, 8, 31)
    assert process._month_due_date(2026, 9, None) == date(2026, 9, 30)


@pytest.mark.parametrize("start,end", [(None, None), (date(2026, 9, 1), None),
    (None, date(2026, 9, 30)), (date(2026, 9, 30), date(2026, 9, 1))])
def test_missing_or_invalid_dates_never_invent_period_tasks(start, end):
    assert process._weekly_due_dates(start, end, {"requiredCount": 3}) == []
    assert process._month_due_dates(start, end, 3) == []
    record = SimpleNamespace(intern_start_date=start, intern_end_date=end)
    batch = SimpleNamespace(start_date=None, end_date=None)
    assert process._record_dates(record, batch) == (start, end)


def test_zero_and_missing_counts_do_not_expand_calendar():
    start, end = date(2026, 9, 1), date(2026, 12, 30)
    assert process._weekly_due_dates(start, end, {}) == []
    assert process._weekly_due_dates(start, end, {"requiredCount": 0}) == []
    assert process._month_due_dates(start, end, 0) == []
    assert process._student_rows([{"weeklySubmitted": 2, "weeklyExpected": 0}])[0]["weeklyCompletionRate"] is None


@pytest.mark.parametrize("group", ["ADVISOR", "HOMEROOM", "COLLEGE", "MAJOR", "CLASS"])
def test_extra_reports_never_cancel_another_students_missing_reports(group):
    facts = []
    for submitted in (3, 0):
        fact = defaultdict(int, weeklySubmitted=submitted, weeklyExpected=1,
                           monthlySubmitted=submitted, monthlyExpected=1,
                           grade="", advisorName="教师", college="学院")
        facts.append(fact)
    row = process._aggregate(facts, group, "测试批次")[0]
    assert row["weeklySubmitted"] == 3
    assert row["weeklyCompletionRate"] == 50.0
    assert row["monthlyCompletionRate"] == 50.0
    if group in {"ADVISOR", "HOMEROOM"}:
        assert row["weeklyMissing"] == 1
