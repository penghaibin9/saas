"""Yiyang C06 four-group procurement statistics acceptance."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

TID = 1000000000000000001
ADMIN = {
    "tenantId": str(TID), "userId": "9001", "realName": "统计管理员",
    "userType": "SCHOOL_ADMIN", "currentRoleCode": "SCHOOL_ADMIN",
}


@pytest.fixture()
def stats_db(tmp_path):
    import app.db.session as db_session
    from app.config import settings
    from app.models import (
        AttendanceException,
        AuditOutbox,
        InternshipAgreement,
        InternshipApplication,
        InternshipArchive,
        InternshipBatch,
        InternshipChangeRequest,
        InternshipCheckin,
        InternshipEnterpriseEval,
        InternshipFinalScore,
        InternshipGuidance,
        InternshipLeave,
        InternshipPayrollStatement,
        InternshipPayrollVersion,
        InternshipRecord,
        InternshipStudentEval,
        InternshipVisit,
        RiskRecord,
        StudentAccountLink,
        StudentProfile,
        User,
        WeeklyReport,
        WxAccountBinding,
    )

    old = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite+pysqlite:///{(tmp_path / 'c06.db').as_posix()}"
    db_session._engine = None
    db_session._factory = None
    engine = db_session.get_engine()
    for table in (
        InternshipBatch.__table__, StudentProfile.__table__, User.__table__,
        StudentAccountLink.__table__, WxAccountBinding.__table__,
        InternshipRecord.__table__, InternshipApplication.__table__,
        InternshipChangeRequest.__table__, InternshipAgreement.__table__,
        InternshipCheckin.__table__, AttendanceException.__table__,
        InternshipLeave.__table__, WeeklyReport.__table__,
        InternshipGuidance.__table__, InternshipVisit.__table__, RiskRecord.__table__,
        InternshipEnterpriseEval.__table__, InternshipStudentEval.__table__,
        InternshipFinalScore.__table__, InternshipArchive.__table__,
        InternshipPayrollStatement.__table__, InternshipPayrollVersion.__table__,
        AuditOutbox.__table__,
    ):
        table.create(bind=engine, checkfirst=True)
    try:
        yield
    finally:
        engine.dispose()
        settings.DATABASE_URL = old
        db_session._engine = None
        db_session._factory = None


def _group(data, key):
    return next(item for item in data["groups"] if item["key"] == key)


def _ratio(group, key):
    return next(item for item in group["ratios"] if item["key"] == key)


def test_c06_four_groups_use_canonical_facts_and_never_mix_currencies(stats_db):
    from app.core.context import set_current_user, set_tenant
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import (
        InternshipApplication,
        InternshipBatch,
        InternshipChangeRequest,
        InternshipFinalScore,
        InternshipPayrollStatement,
        InternshipPayrollVersion,
        InternshipRecord,
        StudentAccountLink,
        StudentProfile,
        User,
        WxAccountBinding,
    )
    from app.modules.internship.services import internship_procurement_stats_service as service

    set_tenant({"tenantId": str(TID)})
    set_current_user(ADMIN)
    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID, batch_name="益阳C06四组统计", batch_no="YIYANG-C06",
            start_date=datetime(2026, 9, 1), end_date=datetime(2026, 11, 9),
            planned_count=3, status="RUNNING",
            rules_config={"weeklyReport": {"frequency": "WEEKLY"}},
        )
        db.add(batch); db.flush()

        records = []
        accounts = []
        for index in range(1, 4):
            student = StudentProfile(
                tenant_id=TID, student_no=f"C06-{index:03d}",
                real_name=f"C06学生{index}",
                current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE",
            )
            db.add(student); db.flush()
            record = InternshipRecord(
                tenant_id=TID, student_id=student.id, batch_id=batch.id,
                enterprise_name=f"企业{index}", position_name=f"岗位{index}",
                position_id=100 + index, destination_type="ASSIGNED",
                eligibility_status="QUALIFIED",
                status="ONBOARD", risk_level="NONE",
                intern_start_date=datetime(2026, 9, 1),
                intern_end_date=datetime(2026, 11, 9),
            )
            db.add(record); db.flush()
            records.append((record, student))

            app = InternshipApplication(
                tenant_id=TID, record_id=record.id, student_id=student.id,
                batch_id=batch.id, campaign_id=None, application_type="SELF_ARRANGED",
                volunteer_no=1, company_name=record.enterprise_name,
                position_name=record.position_name,
                work_city=["长沙市", "长沙市", "益阳市"][index - 1],
                major_match=[True, False, None][index - 1],
                status="APPROVED", reviewed_by_name="统计管理员",
                reviewed_at=datetime(2026, 8, 25, 10, index),
            )
            db.add(app)

            account = User(
                tenant_id=TID, login_name=student.student_no,
                real_name=student.real_name, password_hash=hash_password("Test!Pass123"),
                user_type="STUDENT", status="ACTIVE",
            )
            db.add(account); db.flush()
            accounts.append(account)
            if index <= 2:
                db.add(StudentAccountLink(
                    tenant_id=TID, student_id=student.id, user_id=account.id,
                    link_status="ACTIVE", source="MANUAL",
                    bound_login_name=account.login_name, bound_student_no=student.student_no,
                ))
            if index == 1:
                db.add(WxAccountBinding(
                    tenant_id=TID, wx_openid="wx-c06-001", user_id=account.id, status="ACTIVE"
                ))

        # One of three students has an approved enterprise/position change.
        db.add(InternshipChangeRequest(
            tenant_id=TID, internship_id=records[0][0].id,
            student_id=records[0][1].id, change_type="CHANGE_POSITION",
            reason="根据企业培养计划调整岗位", target_position_id=999,
            target_enterprise_name="企业1", target_position_name="新岗位",
            record_version_snapshot=0, status="APPROVED",
            reviewed_by_name="统计管理员", reviewed_at=datetime(2026, 9, 20),
        ))

        # Published scores: 95 excellent, 80 not excellent; third student has no published score.
        for idx, score in ((0, 95.0), (1, 80.0)):
            record, student = records[idx]
            db.add(InternshipFinalScore(
                tenant_id=TID, internship_id=record.id, student_id=student.id,
                batch_id=batch.id, total_score=score, pass_line=60.0,
                is_pass=True, incomplete=False, status="PUBLISHED",
                w_checkin=20, w_weekly=20, w_monthly=20, w_enterprise=20, w_school=20,
            ))

        # Two CNY versions and one USD version: never cross-currency average.
        payroll_specs = [
            (records[0], "CNY", Decimal("3000.00")),
            (records[1], "CNY", Decimal("4000.00")),
            (records[2], "USD", Decimal("500.00")),
        ]
        for idx, ((record, student), currency, amount) in enumerate(payroll_specs, start=1):
            statement = InternshipPayrollStatement(
                tenant_id=TID, internship_id=record.id, student_id=student.id,
                batch_id=batch.id, pay_month="2026-09", agreed_salary_snapshot=Decimal("3500.00"),
                agreed_salary_currency="CNY", revision_count=1,
            )
            db.add(statement); db.flush()
            version = InternshipPayrollVersion(
                tenant_id=TID, statement_id=statement.id, revision_no=1,
                actual_amount=amount, currency=currency, status="APPROVED",
                is_current=True, submitted_at=datetime(2026, 9, 30, 18, idx),
            )
            db.add(version); db.flush()
            statement.current_version_id = version.id

        db.commit()
        batch_id = batch.id
    finally:
        db.close()

    data = service.overview(ADMIN, batch_id=batch_id)
    assert [group["key"] for group in data["groups"]] == [
        "overview", "destination", "activity", "quality"
    ]

    overview = _group(data, "overview")
    account = _ratio(overview, "accountBindingRate")
    wechat = _ratio(overview, "wechatBindingRate")
    assert (account["numerator"], account["denominator"], account["rate"]) == (2, 3, 66.7)
    assert (wechat["numerator"], wechat["denominator"], wechat["rate"]) == (1, 2, 50.0)

    destination = _group(data, "destination")
    transfer = _ratio(destination, "transferRate")
    stable = _ratio(destination, "stabilityRate")
    assert (transfer["numerator"], transfer["denominator"], transfer["rate"]) == (1, 3, 33.3)
    assert (stable["numerator"], stable["denominator"], stable["rate"]) == (2, 3, 66.7)
    assert destination["cityTop10"] == [
        {"city": "长沙市", "count": 2},
        {"city": "益阳市", "count": 1},
    ]

    quality = _group(data, "quality")
    major = _ratio(quality, "majorMatchRate")
    excellent = _ratio(quality, "excellentRate")
    assert (major["numerator"], major["denominator"], major["rate"]) == (1, 2, 50.0)
    assert (excellent["numerator"], excellent["denominator"], excellent["rate"]) == (1, 2, 50.0)

    wages = {row["currency"]: row for row in quality["wageByCurrency"]}
    assert set(wages) == {"CNY", "USD"}
    assert wages["CNY"]["count"] == 2
    assert wages["CNY"]["averageActualAmount"] == 3500.0
    assert wages["CNY"]["totalActualAmount"] == 7000.0
    assert wages["USD"]["count"] == 1
    assert wages["USD"]["averageActualAmount"] == 500.0
    assert quality["wageRecordCount"] == 3


def test_c06_procurement_stats_routes_are_registered():
    from app.main import app
    paths = set(app.openapi().get("paths", {}))
    assert "/api/v1/internship/stats/procurement-overview" in paths
    assert "/api/v1/mobile/teacher/internship/context/stats/procurement-overview" in paths
