"""Yiyang AP05: exemption application must be a real end-to-end state transition."""
from __future__ import annotations

import pytest

TID = 1000000000000000001
STUDENT = {
    "tenantId": str(TID),
    "userId": "51001",
    "studentNo": "AP05-001",
    "realName": "免实习测试学生",
    "userType": "STUDENT",
    "currentRoleCode": "STUDENT",
}
ADMIN = {
    "tenantId": str(TID),
    "userId": "90001",
    "realName": "AP05审核管理员",
    "userType": "TEACHER",
    "currentRoleCode": "SCHOOL_ADMIN",
}


@pytest.fixture()
def standalone_db(tmp_path):
    import app.db.session as db_session
    from app.config import settings
    from app.models import (
        FileBinding,
        FileObject,
        InternshipApplication,
        InternshipAuditTrail,
        InternshipBatch,
        InternshipRecord,
        StudentProfile,
    )

    old_url = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite+pysqlite:///{(tmp_path / 'yiyang-ap05.db').as_posix()}"
    db_session._engine = None
    db_session._factory = None

    engine = db_session.get_engine()
    for table in (
        InternshipBatch.__table__,
        StudentProfile.__table__,
        InternshipRecord.__table__,
        InternshipApplication.__table__,
        InternshipAuditTrail.__table__,
        FileObject.__table__,
        FileBinding.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    try:
        yield
    finally:
        engine.dispose()
        settings.DATABASE_URL = old_url
        db_session._engine = None
        db_session._factory = None


def _seed():
    from app.db.session import get_sessionmaker
    from app.models import (
        FileObject,
        InternshipApplication,
        InternshipBatch,
        InternshipRecord,
        StudentProfile,
    )

    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="AP05免实习验收批次",
            batch_no="YIYANG-AP05-EXEMPT",
            planned_count=1,
            status="RUNNING",
        )
        db.add(batch)
        db.flush()

        student = StudentProfile(
            tenant_id=TID,
            student_no=STUDENT["studentNo"],
            real_name=STUDENT["realName"],
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
            advisor_name="指导教师",
            eligibility_status="QUALIFIED",
            destination_type="NONE",
            status="PREPARING",
            risk_level="NONE",
        )
        db.add(record)
        db.flush()

        # Sibling current application: approval of exemption must cancel it atomically.
        sibling = InternshipApplication(
            tenant_id=TID,
            record_id=record.id,
            student_id=student.id,
            batch_id=batch.id,
            campaign_id=None,
            application_type="SELF_ARRANGED",
            volunteer_no=0,
            company_name="历史自主实习企业",
            position_name="历史岗位",
            status="DRAFT",
        )
        db.add(sibling)

        evidence = FileObject(
            tenant_id=TID,
            file_key="tests/ap05/exemption-proof.pdf",
            file_name="免实习证明.pdf",
            ext="pdf",
            mime_type="application/pdf",
            size_bytes=128,
            sha256="a" * 64,
            biz_type="INTERNSHIP",
            visibility="PRIVATE",
            security_level="NORMAL",
            status="AVAILABLE",
            storage_backend="local",
            storage_zone="ACTIVE",
            upload_source="USER",
            scan_required=False,
            scan_status="NOT_REQUIRED",
        )
        db.add(evidence)
        db.commit()
        return {
            "batchId": batch.id,
            "recordId": record.id,
            "siblingId": sibling.id,
            "evidenceId": evidence.id,
        }
    finally:
        db.close()


def test_ap05_exemption_save_submit_approve_is_real_flow(standalone_db):
    from sqlalchemy import select

    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import FileBinding, InternshipApplication, InternshipRecord
    from app.modules.internship.services import internship_application_service as svc

    set_tenant({"tenantId": str(TID)})
    set_current_user(STUDENT)
    seeded = _seed()

    draft = svc.save_my(STUDENT, {
        "applicationType": "EXEMPTION",
        "exemptionType": "FURTHER_STUDY",
        "exemptionDestination": "已升学至测试院校",
        "exemptionReason": "已取得正式录取通知，申请免实习",
        "evidenceFileId": str(seeded["evidenceId"]),
        "applicationNote": "已取得正式录取通知，申请免实习",
    })
    assert draft["status"] == "DRAFT"
    assert draft["exemptionType"] == "FURTHER_STUDY"
    assert draft["exemptionDestination"] == "已升学至测试院校"
    assert draft["exemptionReason"] == "已取得正式录取通知，申请免实习"
    assert draft["evidenceFileId"] == str(seeded["evidenceId"])
    assert draft["companyName"] == ""
    assert draft["positionName"] == ""

    db = get_sessionmaker()()
    try:
        binding = db.scalar(select(FileBinding).where(
            FileBinding.tenant_id == TID,
            FileBinding.file_id == seeded["evidenceId"],
            FileBinding.biz_type == "INTERNSHIP_APPLICATION_EVIDENCE",
            FileBinding.biz_id == str(draft["id"]),
            FileBinding.is_deleted.is_(False),
        ))
        assert binding is not None
    finally:
        db.close()

    submitted = svc.submit_my(STUDENT, draft["id"])
    assert submitted["status"] == "PENDING_REVIEW"

    set_current_user(ADMIN)
    approved = svc.review_application(
        submitted["id"],
        "APPROVE",
        "材料真实有效，同意免实习",
        ADMIN,
        expected_version=submitted["version"],
        record_expected_version=submitted["recordVersion"],
        expected_batch_id=seeded["batchId"],
    )
    assert approved["status"] == "APPROVED"

    db = get_sessionmaker()()
    try:
        record = db.get(InternshipRecord, seeded["recordId"])
        sibling = db.get(InternshipApplication, seeded["siblingId"])
        exemption = db.get(InternshipApplication, int(submitted["id"]))
        assert record.destination_type == "EXEMPTED"
        assert record.enterprise_id is None
        assert record.position_id is None
        assert exemption.status == "APPROVED"
        assert sibling.status == "CANCELLED"
    finally:
        db.close()
