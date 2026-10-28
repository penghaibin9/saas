"""Report-derived grade rules use the existing canonical obligation contract."""
from datetime import datetime
from types import SimpleNamespace as Row
from unittest.mock import MagicMock

import pytest

from app.modules.internship.services import internship_score_fact_guard as facts


def snapshot(monkeypatch, rules, *, weekly=0, monthly=0, summary=0, dates=True):
    batch = Row(id=7, rules_config=rules, rules_version=3,
                start_date=datetime(2026, 9, 1) if dates else None,
                end_date=datetime(2026, 12, 30) if dates else None)
    record = Row(id=11, student_id=17, batch_id=7, version=2, status='ASSESSING',
                 intern_start_date=batch.start_date, intern_end_date=batch.end_date)
    weekly_rows = [Row(id=100+i, version=0, report_version=4, week_number=i+1, status='APPROVED')
                   for i in range(weekly)]
    process_rows = [Row(id=200+i, version=0, report_type='MONTHLY', period_key=f'2026-{i+1:02}', status='APPROVED')
                   for i in range(monthly)]
    process_rows += [Row(id=300+i, version=0, report_type='SUMMARY', period_key=f'FINAL-{i}', status='APPROVED')
                    for i in range(summary)]
    db = MagicMock()
    db.get.return_value = batch
    db.scalar.return_value = None
    db.scalars.side_effect = [Row(all=lambda rows=rows: rows)
        for rows in ([], [], [], weekly_rows, process_rows, [], [])]
    monkeypatch.setattr(facts, '_tid', lambda: 1)
    # An old compliance count must not override the report configuration in grade sources.
    monkeypatch.setattr(facts, 'material_quantity_facts', lambda *_: {
        'checkin': {'expected': 2, 'actual': 1}, 'weekly': {'expected': 18, 'actual': 9},
        'guidance': {'expected': 1, 'actual': 0}, 'visit': {'expected': 1, 'actual': 0}})
    monkeypatch.setattr(facts._score, '_approved_enterprise_eval', lambda *_: None)
    monkeypatch.setattr(facts._score, '_active_config', lambda *_: None)
    return facts._fact_snapshot(db, record)


@pytest.mark.parametrize('dates', [True, False])
def test_configured_monthly_and_summary_replace_calendar_denominator(monkeypatch, dates):
    result = snapshot(monkeypatch, {'weeklyReport': {'requiredCount': 1},
        'processReport': {'monthlyRequiredCount': 1, 'summaryRequiredCount': 1}},
        weekly=1, monthly=1, summary=1, dates=dates)
    assert result['manifest']['monthly']['expected'] == 2
    assert result['manifest']['monthly']['actual'] == 2
    assert result['suggestedScores']['monthly'] == result['suggestedScores']['weekly'] == 100
    assert result['suggestedScores']['checkin'] == 50
    assert result['weights'] == {'checkin': 20, 'weekly': 20, 'monthly': 10, 'enterprise': 30, 'school': 20}
    assert result['sourceReadiness'] == {'enterpriseEvaluation': False, 'studentSelfEvaluation': False, 'advisorEvaluation': False}


@pytest.mark.parametrize('weekly_rule', [{}, {'requiredCount': 0}])
def test_unconfigured_weekly_cannot_fall_back_to_period_or_full_marks(monkeypatch, weekly_rule):
    result = snapshot(monkeypatch, {'weeklyReport': weekly_rule}, weekly=3, summary=1)
    assert result['manifest']['weekly']['expected'] == 0
    assert result['suggestedScores']['weekly'] is None
    assert result['suggestedScores']['monthly'] == 100  # Existing default: one summary.


def test_unconfigured_monthly_and_summary_remain_missing_even_with_old_documents(monkeypatch):
    result = snapshot(monkeypatch, {'weeklyReport': {'requiredCount': 1},
        'processReport': {'monthlyRequiredCount': 0, 'summaryRequiredCount': 0}}, monthly=3, summary=1)
    assert result['manifest']['monthly']['expected'] == 0
    assert result['suggestedScores']['monthly'] is None
    assert result['suggestedScores']['weekly'] == 0


def test_extra_monthly_reports_do_not_replace_the_missing_summary(monkeypatch):
    result = snapshot(monkeypatch, {'processReport': {'monthlyRequiredCount': 1, 'summaryRequiredCount': 1}}, monthly=3)
    assert result['manifest']['monthly']['actual'] == 1
    assert len(result['manifest']['monthly']['rows']) == 3
    assert result['suggestedScores']['monthly'] == 50


def test_disabled_monthly_does_not_earn_summary_credit(monkeypatch):
    result = snapshot(monkeypatch, {'processReport': {'monthlyRequiredCount': 0, 'summaryRequiredCount': 1}}, monthly=3)
    assert result['manifest']['monthly']['expected'] == 1
    assert result['manifest']['monthly']['actual'] == 0
    assert result['suggestedScores']['monthly'] == 0


def test_summary_default_stays_one_and_nonreport_zero_denominator_policy_is_unchanged(monkeypatch):
    result = snapshot(monkeypatch, {}, summary=1)
    assert result['manifest']['monthly']['expected'] == 1
    assert result['suggestedScores']['monthly'] == 100
    assert facts._ratio_score(0, 0) == 100
