"""Yiyang G10: internship application coverage/review statistics must use full scoped data."""

from __future__ import annotations

import pytest

TID = 1000000000000000001
USER = {
    "tenantId": str(TID),
    "userId": "90001",
    "realName": "G10验收管理员",
    "userType": "SCHOOL_ADMIN",
    "currentRoleCode": "SCHOOL_ADMIN",
}


@pytest.fixture()
def standalone_db(tmp_path):
    import app.db.session as db_session
    from app.config import settings
    from app.models import (
        EmpCompany,
        InternshipApplication,
        InternshipBatch,
        InternshipPosition,
        InternshipRecord,
        StudentProfile,
    )

    old_url = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite+pysqlite:///{(tmp_path / 'yiyang-g10.db').as_posix()}"
    db_session._engine = None
    db_session._factory = None

    engine = db_session.get_engine()
    for table in (
        EmpCompany.__table__,
        InternshipBatch.__table__,
        StudentProfile.__table__,
        InternshipRecord.__table__,
        InternshipPosition.__table__,
        InternshipApplication.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    try:
        yield
    finally:
        engine.dispose()
        settings.DATABASE_URL = old_url
        db_session._engine = None
        db_session._factory = None


def _seed_g10():
    from app.db.session import get_sessionmaker
    from app.models import InternshipApplication, InternshipBatch, InternshipRecord, StudentProfile

    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="益阳G10统计验收批次",
            batch_no="YIYANG-G10",
            planned_count=65,
            status="RUNNING",
        )
        db.add(batch)
        db.flush()

        for index in range(65):
            student = StudentProfile(
                tenant_id=TID,
                student_no=f"G10-{index + 1:03d}",
                real_name=f"G10学生{index + 1:03d}",
                current_stage="INTERNSHIP",
                student_status="NORMAL",
                status="ACTIVE",
            )
            db.add(student)
            db.flush()

            record = InternshipRecord(
                tenant_id=TID,
                student_id=student.id,
                batch_id=batch.id,
                advisor_name="G10指导老师",
                eligibility_status="QUALIFIED",
                destination_type="NONE",
                status="PREPARING",
                risk_level="NONE",
            )
            db.add(record)
            db.flush()

            if index < 45:
                status = "PENDING_REVIEW" if index < 30 else ("APPROVED" if index < 40 else "REJECTED")
                db.add(InternshipApplication(
                    tenant_id=TID,
                    record_id=record.id,
                    student_id=student.id,
                    batch_id=batch.id,
                    campaign_id=None,
                    application_type="SELF_ARRANGED",
                    volunteer_no=0,
                    company_name=f"G10企业{index + 1:03d}",
                    position_name="测试岗位",
                    work_address="湖南省益阳市",
                    contact_name="企业联系人",
                    contact_phone="13800138000",
                    status=status,
                ))
        db.commit()
        return batch.id
    finally:
        db.close()


def test_g10_full_scope_counts_and_drilldown_are_not_page_length(standalone_db):
    from app.core.context import set_current_user, set_tenant
    from app.modules.internship.services import internship_application_service as svc

    set_tenant({"tenantId": str(TID)})
    set_current_user(USER)
    batch_id = _seed_g10()

    pending_items, pending_total = svc.list_applications(
        1, 20, status="PENDING_REVIEW", batch_id=batch_id, user=USER
    )
    assert pending_total == 30
    assert len(pending_items) == 20

    summary = svc.application_summary(batch_id=batch_id, user=USER)
    assert summary["totalStudents"] == 65
    assert summary["filledStudents"] == 45
    assert summary["unfilledStudents"] == 20
    assert summary["filledRate"] == 69.2
    assert summary["pendingReviewApplications"] == 30
    assert summary["reviewedApplications"] == 15
    assert summary["approvedApplications"] == 10
    assert summary["rejectedApplications"] == 5

    reviewed_items, reviewed_total = svc.list_applications(
        1, 20, status="REVIEWED", batch_id=batch_id, user=USER
    )
    assert reviewed_total == 15
    assert len(reviewed_items) == 15

    unfilled_items, unfilled_total = svc.list_application_students(
        1, 100, "UNFILLED", batch_id=batch_id, user=USER
    )
    assert unfilled_total == 20
    assert len(unfilled_items) == 20
    assert all(item["applicationState"] == "UNFILLED" for item in unfilled_items)

    filled_items, filled_total = svc.list_application_students(
        1, 20, "FILLED", batch_id=batch_id, user=USER
    )
    assert filled_total == 45
    assert len(filled_items) == 20
    assert all(item["applicationState"] == "FILLED" for item in filled_items)
