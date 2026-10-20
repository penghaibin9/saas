"""Yiyang C08 ordinary procurement contracts for AP16 and AP19-AP24.

These tests are intentionally narrow contracts. Full MySQL/browser acceptance is deferred until
the implementation batch is complete; this file prevents route/schema drift meanwhile.
"""
import pytest
from pydantic import ValidationError

from app.api.v1.teacher_mobile_internship import router as teacher_mobile_router
from app.models import InternshipTeacherCheckin, InternshipTeacherMakeup
from app.modules.internship.routers.internship_stats import router as stats_router
from app.modules.internship.schemas.internship import RulesConfig
from app.modules.internship.services import internship_process_statistics_service as process_stats


def _routes(router):
    return {
        (route.path, method)
        for route in router.routes
        for method in (getattr(route, "methods", set()) or set())
    }


def test_ap16_teacher_makeup_is_separate_request_and_materialized_checkin_fact():
    assert InternshipTeacherMakeup.__tablename__ == "t_internship_teacher_makeup"
    assert InternshipTeacherCheckin.__tablename__ == "t_internship_teacher_checkin"
    table = InternshipTeacherMakeup.__table__
    for name in (
        "batch_id", "teacher_user_id", "local_date", "reason", "evidence_file_id",
        "status", "active_pending_key", "reviewed_by_name", "reviewed_at", "review_comment",
    ):
        assert name in table.c


def test_ap16_mobile_and_admin_routes_cover_apply_review_and_excel():
    mobile = _routes(teacher_mobile_router)
    staff = _routes(stats_router)
    assert ("/internship/activity/makeups", "GET") in mobile
    assert ("/internship/activity/makeups", "POST") in mobile
    assert ("/internship/activity/makeups/{makeup_id}/withdraw", "POST") in mobile
    assert ("/internship/teacher-management", "GET") in staff
    assert ("/internship/teacher-management/export", "POST") in staff
    assert ("/internship/teacher-management/makeups", "GET") in staff
    assert ("/internship/teacher-management/makeups/{makeupId}/review", "POST") in staff


def test_ap19_ap24_routes_cover_same_condition_screen_and_excel():
    staff = _routes(stats_router)
    assert ("/internship/stats/process-analytics", "GET") in staff
    assert ("/internship/stats/process-analytics/export", "POST") in staff


def test_ap19_ap24_column_contract_contains_procurement_minimums():
    required = {
        "STUDENT": {
            "studentName", "studentNo", "grade", "batchName", "college", "major",
            "className", "advisorName", "headTeacherName", "enterpriseCount",
            "expectedCheckins", "actualCheckins", "leaveDays", "exemptDays", "makeupDays",
            "dailySubmitted", "weeklyExpected", "weeklySubmitted", "weeklyLate",
            "weeklyCompletionRate", "monthlyExpected", "monthlySubmitted",
            "summarySubmitted", "totalScore",
        },
        "ADVISOR": {
            "name", "employeeNo", "college", "internshipType", "studentCount", "boundCount",
            "checkinCount", "averageCheckins", "averageCheckinRate", "dailyCount",
            "weeklyExpected", "weeklySubmitted", "weeklyMissing", "weeklyReviewed",
            "weeklyReviewRate", "weeklyTimelyReviewRate", "monthlySubmitted",
            "monthlyCompletionRate", "monthlyReviewRate", "monthlyTimelyReviewRate",
            "summarySubmitted", "summaryReviewRate",
        },
        "HOMEROOM": {
            "name", "employeeNo", "college", "className", "internshipType", "studentCount",
            "boundCount", "checkinCount", "averageCheckinRate", "dailyCount",
            "weeklySubmitted", "weeklyCompletionRate", "weeklyReviewed",
            "weeklyReviewRate", "weeklyTimelyReviewRate", "monthlySubmitted",
            "monthlyCompletionRate", "monthlyReviewRate", "summarySubmitted",
            "summaryReviewRate",
        },
        "COLLEGE": {
            "college", "grades", "studentCount", "internshipStudentCount", "boundCount",
            "bindingRate", "exemptInternshipCount", "onboardCount", "onboardRate",
            "majorMatchRate", "stabilityRate", "averageCheckins", "checkinRate", "dailyCount",
            "weeklyExpected", "weeklySubmitted", "weeklyCompletionRate", "weeklyReviewed",
            "weeklyReviewRate", "monthlySubmitted", "monthlyCompletionRate",
            "monthlyReviewed", "monthlyReviewRate", "summarySubmitted",
        },
        "MAJOR": {"college", "grades", "major"},
        "CLASS": {"college", "grades", "major", "className", "headTeacherName"},
    }
    for group, keys in required.items():
        available = {key for key, _label in process_stats.COLUMN_SETS[group]}
        assert keys <= available


def test_ap19_ap24_rule_config_keeps_required_counts_and_review_sla():
    rules = RulesConfig(
        weeklyReport={
            "frequency": "WEEKLY",
            "minWordCount": 30,
            "requiredCount": 12,
            "deadlineWeekday": 5,
            "reviewSlaHours": 36,
        },
        processReport={
            "dailyMinWords": 30,
            "dailyRequiredCount": 60,
            "monthlyMinWords": 100,
            "monthlyRequiredCount": 6,
            "summaryMinWords": 300,
            "summaryRequiredCount": 1,
            "maxImages": 9,
            "maxVideos": 3,
            "reviewSlaHours": 48,
        },
    ).model_dump()
    assert rules["weeklyReport"]["requiredCount"] == 12
    assert rules["weeklyReport"]["reviewSlaHours"] == 36
    assert rules["processReport"]["dailyRequiredCount"] == 60
    assert rules["processReport"]["monthlyRequiredCount"] == 6
    assert rules["processReport"]["summaryRequiredCount"] == 1
    assert rules["processReport"]["reviewSlaHours"] == 48

    with pytest.raises(ValidationError):
        RulesConfig(processReport={"summaryRequiredCount": 2})


def test_ap19_ap24_week_and_month_windows_are_explicit():
    mode, start, end = process_stats._window("WEEK", "2026-09-28")
    assert mode == "WEEK"
    assert start.isoformat() == "2026-09-28"
    assert end.isoformat() == "2026-10-04"

    mode, start, end = process_stats._window("MONTH", "2026-09-28")
    assert mode == "MONTH"
    assert start.isoformat() == "2026-09-01"
    assert end.isoformat() == "2026-09-30"


def test_ap19_ap24_custom_columns_fail_closed():
    selected = process_stats._selected_columns("STUDENT", "studentName,weeklyCompletionRate")
    assert [key for key, _label in selected] == ["studentName", "weeklyCompletionRate"]
    with pytest.raises(Exception):
        process_stats._selected_columns("STUDENT", "studentName,notARealColumn")
