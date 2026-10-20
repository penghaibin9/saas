"""Yiyang G02: complete internship position submission is persisted and reviewable."""

from __future__ import annotations

from datetime import datetime

import pytest

TID = 1000000000000000001
STUDENT = {
    "tenantId": str(TID),
    "userId": "20001",
    "studentNo": "YIYANG-G02-001",
    "realName": "益阳G02学生",
    "userType": "STUDENT",
    "currentRoleCode": "STUDENT",
}
ADMIN = {
    "tenantId": str(TID),
    "userId": "90001",
    "realName": "益阳G02审核员",
    "userType": "SCHOOL_ADMIN",
    "currentRoleCode": "SCHOOL_ADMIN",
}


@pytest.fixture()
def standalone_db(tmp_path, monkeypatch):
    import app.db.session as db_session
    from app.config import settings
    from app.models import (
        AuditOutbox,
        InternshipApplication,
        FileBinding,
        FileObject,
        InternshipAuditTrail,
        InternshipBatch,
        InternshipRecord,
        StudentProfile,
    )

    old_url = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite+pysqlite:///{(tmp_path / 'yiyang-g02.db').as_posix()}"
    db_session._engine = None
    db_session._factory = None

    engine = db_session.get_engine()
    for table in (
        InternshipBatch.__table__,
        StudentProfile.__table__,
        InternshipRecord.__table__,
        InternshipApplication.__table__,
        InternshipAuditTrail.__table__,
        AuditOutbox.__table__,
        FileObject.__table__,
        FileBinding.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    db = db_session.get_sessionmaker()()
    try:
        for file_id, name in (
            (9101, "g02-evidence.pdf"),
            (9102, "g02-agreement-1.jpg"),
            (9103, "g02-agreement-2.jpg"),
        ):
            db.add(FileObject(
                id=file_id,
                tenant_id=TID,
                file_key=f"g02/{name}",
                file_name=name,
                ext=name.rsplit(".", 1)[-1],
                mime_type="application/pdf" if name.endswith(".pdf") else "image/jpeg",
                size_bytes=128,
                sha256=(f"{file_id:064x}")[-64:],
                visibility="PRIVATE",
                security_level="NORMAL",
                status="AVAILABLE",
                storage_backend="local",
                storage_zone="ACTIVE",
                upload_source="SYSTEM",
                scan_required=False,
                scan_status="NOT_REQUIRED",
                scan_attempts=0,
            ))
        db.commit()
    finally:
        db.close()

    try:
        yield
    finally:
        engine.dispose()
        settings.DATABASE_URL = old_url
        db_session._engine = None
        db_session._factory = None


def _seed_student_record():
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile

    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="益阳G02完整岗位填报验收",
            batch_no="YIYANG-G02",
            start_date=datetime(2026, 9, 1),
            end_date=datetime(2027, 1, 31),
            planned_count=1,
            status="RUNNING",
        )
        student = StudentProfile(
            tenant_id=TID,
            student_no=STUDENT["studentNo"],
            real_name=STUDENT["realName"],
            current_stage="INTERNSHIP",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add_all([batch, student])
        db.flush()
        record = InternshipRecord(
            tenant_id=TID,
            student_id=student.id,
            batch_id=batch.id,
            advisor_name="校内指导老师",
            eligibility_status="QUALIFIED",
            destination_type="NONE",
            status="PREPARING",
            risk_level="NONE",
        )
        db.add(record)
        db.commit()
        return batch.id, record.id
    finally:
        db.close()


def _payload(batch_id, record_id):
    return {
        "batchId": str(batch_id),
        "internshipId": str(record_id),
        "applicationType": "SELF_ARRANGED",
        "applicationNote": "岗位与专业方向匹配，申请自主实习。",
        "companyName": "益阳示例智能制造有限公司",
        "companyCreditCode": "91430900MA4L12345X",
        "companyPrincipal": "张负责人",
        "companyScale": "中型",
        "companyPhone": "0737-1234567",
        "companyEmail": "hr@example.com",
        "companyNature": "民营企业",
        "companyIndustry": "制造业",
        "companyRegisteredAddress": "湖南省益阳市赫山区示例大道88号",
        "companyPostalCode": "413000",
        "companyProvince": "湖南省",
        "companyCity": "益阳市",
        "companyDistrict": "赫山区",
        "contactName": "李人事",
        "contactPhone": "13800138000",
        "internshipDepartment": "智能制造部",
        "positionName": "设备运维实习生",
        "positionCategory": "工程技术",
        "workContent": "参与设备巡检、维护记录和生产现场技术支持。",
        "enterpriseMentorName": "王工程师",
        "enterpriseMentorPhone": "13900139000",
        "workCountry": "中国",
        "workProvince": "湖南省",
        "workCity": "益阳市",
        "workDistrict": "赫山区",
        "workAddress": "湖南省益阳市赫山区产业园A区",
        "internshipStartDate": "2026-10-01",
        "internshipEndDate": "2027-01-15",
        "internshipMode": "自主实习",
        "majorMatch": True,
        "agreedSalary": "2800.00",
        "evidenceFileId": "9101",
        "agreementFileIds": ["9102", "9103"],
        # A malicious/student-supplied claim must never create a fake green verification state.
        "registryVerificationStatus": "VERIFIED",
        "registryVerificationProvider": "student-self-claimed",
    }


def test_g02_complete_position_roundtrip_and_review(standalone_db):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import InternshipApplication, InternshipRecord
    from app.modules.internship.services import internship_application_service as legacy
    from app.modules.internship.services import internship_student_application_context_service as context

    set_tenant({"tenantId": str(TID)})
    set_current_user(STUDENT)
    batch_id, record_id = _seed_student_record()

    draft = context.save(STUDENT, _payload(batch_id, record_id))
    assert draft["status"] == "DRAFT"
    assert draft["companyName"] == "益阳示例智能制造有限公司"
    assert draft["companyCreditCode"] == "91430900MA4L12345X"
    assert draft["companyScale"] == "中型"
    assert draft["companyNature"] == "民营企业"
    assert draft["companyIndustry"] == "制造业"
    assert draft["internshipDepartment"] == "智能制造部"
    assert draft["positionCategory"] == "工程技术"
    assert draft["enterpriseMentorName"] == "王工程师"
    assert draft["internshipStartDate"] == "2026-10-01"
    assert draft["internshipEndDate"] == "2027-01-15"
    assert draft["majorMatch"] is True
    assert draft["agreedSalary"] == 2800.0
    assert draft["agreementFileIds"] == ["9102", "9103"]
    assert draft["companyRegistryStatus"] == "UNVERIFIED"
    assert draft["companyRegistryVerified"] is False
    assert draft["companyRegistryProvider"] == ""

    submitted = context.submit(
        STUDENT,
        draft["id"],
        {
            "batchId": str(batch_id),
            "internshipId": str(record_id),
            "expectedVersion": draft["version"],
        },
    )
    assert submitted["status"] == "PENDING_REVIEW"
    assert submitted["companyCreditCode"] == "91430900MA4L12345X"
    assert submitted["companyEmail"] == "hr@example.com"
    assert submitted["workContent"].startswith("参与设备巡检")
    assert submitted["companyRegistryVerified"] is False

    set_current_user(ADMIN)
    reviewed = legacy.review_application(
        submitted["id"],
        "APPROVE",
        "材料核验通过",
        ADMIN,
        expected_version=submitted["version"],
        record_expected_version=submitted["recordVersion"],
        expected_batch_id=str(batch_id),
    )
    assert reviewed["status"] == "APPROVED"

    db = get_sessionmaker()()
    try:
        application = db.get(InternshipApplication, int(submitted["id"]))
        record = db.get(InternshipRecord, int(record_id))
        from app.models import FileBinding
        bindings = list(db.query(FileBinding).filter(
            FileBinding.tenant_id == TID,
            FileBinding.biz_id == str(application.id),
            FileBinding.is_deleted.is_(False),
        ).all())
        assert {(row.file_id, row.biz_type) for row in bindings} == {
            (9101, "INTERNSHIP_APPLICATION_EVIDENCE"),
            (9102, "INTERNSHIP_APPLICATION_AGREEMENT"),
            (9103, "INTERNSHIP_APPLICATION_AGREEMENT"),
        }
        assert application.company_credit_code == "91430900MA4L12345X"
        assert application.registry_verification_status == "UNVERIFIED"
        assert record.destination_type == "SELF_ARRANGED"
        assert record.enterprise_name == "益阳示例智能制造有限公司"
        assert record.position_name == "设备运维实习生"
        assert record.enterprise_mentor_name == "王工程师"
        assert record.intern_start_date.date().isoformat() == "2026-10-01"
        assert record.intern_end_date.date().isoformat() == "2027-01-15"
    finally:
        db.close()


def test_g02_rejects_invalid_identity_and_date_order(standalone_db):
    from app.core.context import set_current_user, set_tenant
    from app.modules.internship.services import internship_application_service as legacy

    set_tenant({"tenantId": str(TID)})
    set_current_user(STUDENT)

    payload = _payload(1, 1)
    payload["companyCreditCode"] = "123"
    with pytest.raises(Exception) as exc:
        legacy._clean_self_arranged(payload, require_complete=True)
    assert "统一社会信用代码" in str(exc.value)

    payload = _payload(1, 1)
    payload["internshipStartDate"] = "2027-02-01"
    payload["internshipEndDate"] = "2027-01-01"
    with pytest.raises(Exception) as exc:
        legacy._clean_self_arranged(payload, require_complete=True)
    assert "结束日期" in str(exc.value)
