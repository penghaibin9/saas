"""Yiyang C06 / G14 procurement statistic semantics."""
from __future__ import annotations

from datetime import datetime

import pytest

TID = 1000000000000000001
ADMIN = {
    "tenantId": str(TID), "userId": "9001", "realName": "G14管理员",
    "userType": "SCHOOL_ADMIN", "currentRoleCode": "SCHOOL_ADMIN",
}


@pytest.fixture()
def g14_db(tmp_path):
    import app.db.session as db_session
    from app.config import settings
    from app.models import (
        InternshipAgreement, InternshipArchive, InternshipApplication, InternshipBatch,
        InternshipCheckin, InternshipEnterpriseEval, InternshipFinalScore,
        InternshipGuidance, InternshipLeave, InternshipRecord, InternshipStudentEval,
        InternshipVisit, RiskRecord, StudentProfile, WeeklyReport,
    )

    old = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite+pysqlite:///{(tmp_path / 'g14.db').as_posix()}"
    db_session._engine = None
    db_session._factory = None
    engine = db_session.get_engine()
    for table in (
        InternshipBatch.__table__, StudentProfile.__table__, InternshipRecord.__table__,
        InternshipApplication.__table__, InternshipAgreement.__table__,
        InternshipCheckin.__table__, InternshipLeave.__table__, WeeklyReport.__table__,
        InternshipGuidance.__table__, InternshipVisit.__table__, RiskRecord.__table__,
        InternshipEnterpriseEval.__table__, InternshipStudentEval.__table__,
        InternshipFinalScore.__table__, InternshipArchive.__table__,
    ):
        table.create(bind=engine, checkfirst=True)
    try:
        yield
    finally:
        engine.dispose()
        settings.DATABASE_URL = old
        db_session._engine = None
        db_session._factory = None


def _metric(data, key):
    return next(item for item in data["metrics"] if item["key"] == key)


def test_g14_assignment_is_not_major_match_and_one_of_ten_reports_is_ten_percent(g14_db):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import InternshipApplication, InternshipBatch, InternshipRecord, StudentProfile, WeeklyReport
    from app.modules.internship.services import internship_stats_service as stats

    set_tenant({"tenantId": str(TID)})
    set_current_user(ADMIN)
    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="益阳G14指标口径",
            batch_no="YIYANG-G14",
            start_date=datetime(2026, 9, 1),
            end_date=datetime(2026, 11, 9),
            planned_count=1,
            status="RUNNING",
            rules_config={
                "weeklyReport": {
                    "frequency": "WEEKLY",
                    "minWordCount": 800,
                    "deadlineWeekday": 7,
                }
            },
        )
        student = StudentProfile(
            tenant_id=TID, student_no="G14-001", real_name="G14学生",
            current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE",
        )
        db.add_all([batch, student]); db.flush()
        record = InternshipRecord(
            tenant_id=TID,
            student_id=student.id,
            batch_id=batch.id,
            enterprise_name="益阳某企业",
            position_name="测试岗位",
            position_id=12345,
            destination_type="ASSIGNED",
            eligibility_status="QUALIFIED",
            status="ONBOARD",
            risk_level="NONE",
            intern_start_date=datetime(2026, 9, 1),
            intern_end_date=datetime(2026, 11, 9),
        )
        db.add(record); db.flush()
        db.add(InternshipApplication(
            tenant_id=TID,
            record_id=record.id,
            student_id=student.id,
            batch_id=batch.id,
            campaign_id=None,
            application_type="SELF_ARRANGED",
            volunteer_no=1,
            company_name=record.enterprise_name,
            position_name=record.position_name,
            major_match=False,
            status="APPROVED",
            reviewed_by_name="G14管理员",
            reviewed_at=datetime(2026, 8, 28, 10, 0),
        ))
        db.add(WeeklyReport(
            tenant_id=TID,
            internship_id=record.id,
            week_number=1,
            work_content="第1周工作",
            harvest_content="学习收获",
            plan_content="下周计划",
            word_count=900,
            report_version=1,
            submitted_at=datetime(2026, 9, 7, 18, 0),
            status="APPROVED",
        ))
        db.commit()
        batch_id = batch.id
        record_id = record.id
    finally:
        db.close()

    data = stats.overview(ADMIN, batch_id=batch_id)
    placement = _metric(data, "placementRate")
    legacy_match = _metric(data, "matchRate")
    major = _metric(data, "majorMatchRate")
    reports = _metric(data, "reportTaskCompletionRate")

    assert placement["numerator"] == 1 and placement["denominator"] == 1
    assert placement["rate"] == 100.0
    assert legacy_match["rate"] == 100.0

    # The procurement metric must not reuse assignment/match rate.
    assert major["numerator"] == 0
    assert major["denominator"] == 1
    assert major["rate"] == 0.0

    # Sep 1 through Nov 9 = 70 days = exactly ten weekly tasks.
    assert reports["numerator"] == 1
    assert reports["denominator"] == 10
    assert reports["rate"] == 10.0
    assert data["procurementFacts"]["weeklyReportTasks"]["expected"] == 10
    assert data["procurementFacts"]["weeklyReportTasks"]["submitted"] == 1

    major_den = stats.metric_drilldown(
        ADMIN, "majorMatchRate", "denominator",
        page=1, page_size=20, batch_id=batch_id,
    )
    assert major_den["total"] == 1
    assert major_den["items"][0]["internshipId"] == str(record_id)
    assert major_den["items"][0]["majorMatch"] is False

    report_den = stats.metric_drilldown(
        ADMIN, "reportTaskCompletionRate", "denominator",
        page=1, page_size=20, batch_id=batch_id,
    )
    assert report_den["total"] == 1
    assert report_den["items"][0]["weeklyExpected"] == 10
    assert report_den["items"][0]["weeklySubmitted"] == 1


def test_g14_zero_denominator_is_not_fabricated_as_one_hundred_percent(g14_db):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch
    from app.modules.internship.services import internship_stats_service as stats

    set_tenant({"tenantId": str(TID)})
    set_current_user(ADMIN)
    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="益阳G14空批次",
            batch_no="YIYANG-G14-EMPTY",
            planned_count=0,
            status="RUNNING",
            rules_config={"weeklyReport": {"frequency": "WEEKLY"}},
        )
        db.add(batch); db.commit(); batch_id = batch.id
    finally:
        db.close()

    data = stats.overview(ADMIN, batch_id=batch_id)
    for key in ("majorMatchRate", "reportTaskCompletionRate", "scorePublishRate"):
        metric = _metric(data, key)
        assert metric["denominator"] == 0
        assert metric["rate"] is None
        assert metric["warn"] is False


def test_g14_metric_definitions_expose_procurement_meaning():
    from app.modules.internship.services import internship_stats_service as stats
    definitions = {item["key"]: item for item in stats.metric_definitions()["definitions"]}
    assert definitions["majorMatchRate"]["label"] == "专业对口率"
    assert "major_match" in definitions["majorMatchRate"]["note"]
    assert definitions["reportTaskCompletionRate"]["denominatorLabel"] == "按实习周期和批次频率应交篇数"
