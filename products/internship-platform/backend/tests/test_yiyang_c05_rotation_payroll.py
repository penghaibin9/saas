"""Yiyang C05 / G12-G13 targeted acceptance."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

TID = 1000000000000000001
ADMIN = {
    "tenantId": str(TID), "userId": "9001", "realName": "C05指导教师",
    "userType": "SCHOOL_ADMIN", "currentRoleCode": "SCHOOL_ADMIN",
}
STUDENT = {
    "tenantId": str(TID), "userId": "2001", "studentId": "", "studentNo": "C05-001",
    "realName": "C05学生", "userType": "STUDENT", "currentRoleCode": "STUDENT",
}


@pytest.fixture()
def c05_db(tmp_path):
    import app.db.session as db_session
    from app.config import settings
    from app.models import (
        AuditOutbox,
        FileAsset,
        FileBinding,
        FileObject,
        FileVersion,
        InternshipApplication,
        InternshipAuditTrail,
        InternshipBatch,
        InternshipPayrollStatement,
        InternshipPayrollVersion,
        InternshipRecord,
        InternshipRotation,
        InternshipRotationProject,
        StudentProfile,
    )

    old_url = settings.DATABASE_URL
    old_storage = settings.FILE_STORAGE_DIR
    settings.DATABASE_URL = f"sqlite+pysqlite:///{(tmp_path / 'c05.db').as_posix()}"
    settings.FILE_STORAGE_DIR = str(tmp_path / "files")
    db_session._engine = None
    db_session._factory = None
    from app.services import storage as storage_service
    storage_service._backend = None
    engine = db_session.get_engine()

    for table in (
        InternshipBatch.__table__,
        StudentProfile.__table__,
        InternshipRecord.__table__,
        InternshipApplication.__table__,
        FileObject.__table__,
        FileAsset.__table__,
        FileVersion.__table__,
        FileBinding.__table__,
        InternshipRotation.__table__,
        InternshipRotationProject.__table__,
        InternshipPayrollStatement.__table__,
        InternshipPayrollVersion.__table__,
        InternshipAuditTrail.__table__,
        AuditOutbox.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    try:
        yield
    finally:
        engine.dispose()
        settings.DATABASE_URL = old_url
        settings.FILE_STORAGE_DIR = old_storage
        db_session._engine = None
        db_session._factory = None
        storage_service._backend = None


def _seed():
    from app.db.session import get_sessionmaker
    from app.models import InternshipApplication, InternshipBatch, InternshipRecord, StudentProfile

    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="益阳C05轮岗工资验收",
            batch_no="YIYANG-C05",
            start_date=datetime(2026, 9, 1),
            end_date=datetime(2027, 1, 31),
            planned_count=1,
            status="RUNNING",
            rules_config={"rotationScoreWeights": {"theory": 20, "skill": 50, "mentor": 30}},
        )
        student = StudentProfile(
            tenant_id=TID, student_no=STUDENT["studentNo"], real_name=STUDENT["realName"],
            current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE",
        )
        db.add_all([batch, student]); db.flush()
        record = InternshipRecord(
            tenant_id=TID, student_id=student.id, batch_id=batch.id,
            enterprise_name="益阳C05企业", position_name="生产技术实习生",
            advisor_name="C05指导教师", eligibility_status="QUALIFIED",
            destination_type="SELF_ARRANGED", status="ONBOARD", risk_level="NONE",
            intern_start_date=datetime(2026, 9, 1), intern_end_date=datetime(2027, 1, 31),
        )
        db.add(record); db.flush()
        application = InternshipApplication(
            tenant_id=TID,
            record_id=record.id,
            student_id=student.id,
            batch_id=batch.id,
            campaign_id=None,
            application_type="SELF_ARRANGED",
            volunteer_no=1,
            company_name=record.enterprise_name,
            position_name=record.position_name,
            agreed_salary=Decimal("3500.00"),
            status="APPROVED",
            reviewed_by_name="C05指导教师",
            reviewed_at=datetime(2026, 8, 28, 10, 0),
        )
        db.add(application)
        db.commit()
        return batch.id, student.id, record.id
    finally:
        db.close()


def _image(name: str, content: bytes):
    from app.services import file_service
    return file_service.store_bytes(
        content,
        name,
        biz_type="TEMP_PRIVATE",
        mime_type="image/jpeg",
        user=STUDENT,
        visibility="PRIVATE",
        security_level="PERSONAL",
    )


def test_g12_two_rotation_departments_keep_independent_projects_and_scores(c05_db):
    from app.core.context import set_current_user, set_tenant
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_rotation_service as rotations

    set_tenant({"tenantId": str(TID)})
    set_current_user(ADMIN)
    batch_id, student_id, record_id = _seed()
    STUDENT["studentId"] = str(student_id)

    first = rotations.create_rotation(record_id, {
        "batchId": str(batch_id),
        "departmentName": "生产一部",
        "departmentManagerName": "部门经理甲",
        "mentorName": "带教老师甲",
        "startDate": "2026-09-01",
        "endDate": "2026-09-30",
        "projects": [
            {"projectName": "工艺巡检", "projectContent": "完成工艺巡检与缺陷记录"},
            {"projectName": "设备点检", "projectContent": "参与设备日常点检"},
        ],
    }, ADMIN)
    second = rotations.create_rotation(record_id, {
        "batchId": str(batch_id),
        "departmentName": "质量二部",
        "departmentManagerName": "部门经理乙",
        "mentorName": "带教老师乙",
        "startDate": "2026-10-01",
        "endDate": "2026-10-31",
        "projects": [
            {"projectName": "质量抽检", "projectContent": "独立完成抽检记录"},
        ],
    }, ADMIN)
    assert first["rotationSeq"] == 1
    assert second["rotationSeq"] == 2

    with pytest.raises(AppException) as exc:
        rotations.create_rotation(record_id, {
            "batchId": str(batch_id),
            "departmentName": "重叠部门",
            "mentorName": "带教老师丙",
            "startDate": "2026-09-20",
            "endDate": "2026-10-05",
            "projects": [{"projectName": "重叠项目"}],
        }, ADMIN)
    assert exc.value.code == "DATA_CONFLICT"

    set_current_user(STUDENT)
    first_self = rotations.submit_self_evaluation(first["id"], {
        "batchId": str(batch_id), "internshipId": str(record_id),
        "selfEvaluation": "在生产一部完成工艺巡检和设备点检，能够独立记录异常并按要求复盘改进。",
        "selfRating": 4,
        "expectedVersion": first["version"],
    }, STUDENT)
    second_self = rotations.submit_self_evaluation(second["id"], {
        "batchId": str(batch_id), "internshipId": str(record_id),
        "selfEvaluation": "在质量二部参与质量抽检，掌握抽样记录和问题反馈流程，后续需要提升分析能力。",
        "selfRating": 5,
        "expectedVersion": second["version"],
    }, STUDENT)

    set_current_user(ADMIN)
    first_done = rotations.evaluate_rotation(first["id"], {
        "batchId": str(batch_id),
        "theoryScore": 80,
        "skillScore": 90,
        "mentorScore": 85,
        "comment": "生产一部轮岗完成",
        "expectedVersion": first_self["version"],
    }, ADMIN)
    second_done = rotations.evaluate_rotation(second["id"], {
        "batchId": str(batch_id),
        "theoryScore": 70,
        "skillScore": 75,
        "mentorScore": 80,
        "comment": "质量二部轮岗完成",
        "expectedVersion": second_self["version"],
    }, ADMIN)

    assert first_done["scores"]["rule"] == {
        "theory": 20, "skill": 50, "mentor": 30, "source": "BATCH_RULES"
    }
    assert first_done["scores"]["total"] == 86.5
    assert second_done["scores"]["total"] == 75.5

    rows = rotations.list_for_record(record_id, ADMIN, batch_id=batch_id)
    assert [row["departmentName"] for row in rows] == ["生产一部", "质量二部"]
    assert rows[0]["projects"][0]["projectName"] == "工艺巡检"
    assert rows[0]["scores"]["total"] == 86.5
    assert rows[1]["projects"][0]["projectName"] == "质量抽检"
    assert rows[1]["scores"]["total"] == 75.5
    assert rows[0]["studentSelfRating"] == 4
    assert rows[1]["studentSelfRating"] == 5

    set_current_user(STUDENT)
    with pytest.raises(AppException) as exc:
        rotations.submit_self_evaluation(first["id"], {
            "batchId": str(batch_id), "internshipId": str(record_id),
            "selfEvaluation": "试图在成绩完成以后修改既有自评，这一操作应被拒绝以保护历史事实。",
            "selfRating": 5,
            "expectedVersion": first_done["version"],
        }, STUDENT)
    assert exc.value.code == "DATA_CONFLICT"


def test_g13_monthly_payroll_duplicate_correction_photo_currency_and_agreed_salary(c05_db):
    from app.core.context import set_current_user, set_tenant
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_payroll_service as payrolls

    set_tenant({"tenantId": str(TID)})
    set_current_user(ADMIN)
    batch_id, student_id, record_id = _seed()
    STUDENT["studentId"] = str(student_id)

    set_current_user(STUDENT)
    photo_v1 = _image("2026-09工资凭证_v1.jpg", b"image-v1-payroll")
    first = payrolls.submit_my(STUDENT, {
        "batchId": str(batch_id), "internshipId": str(record_id),
        "payMonth": "2026-09",
        "actualAmount": "3200.00",
        "currency": "CNY",
        "paidOn": "2026-09-30",
        "evidenceFileId": photo_v1["fileId"],
        "submitNote": "首次工资单",
    })
    assert first["agreedSalary"] == 3500.0
    assert first["current"]["actualAmount"] == 3200.0
    assert first["current"]["currency"] == "CNY"
    assert first["current"]["revisionNo"] == 1
    assert first["current"]["evidenceSha256"] == photo_v1["sha256"]

    photo_duplicate = _image("2026-09工资凭证_重复.jpg", b"duplicate-image")
    with pytest.raises(AppException) as exc:
        payrolls.submit_my(STUDENT, {
            "batchId": str(batch_id), "internshipId": str(record_id),
            "payMonth": "2026-09",
            "actualAmount": "3250.00",
            "currency": "CNY",
            "evidenceFileId": photo_duplicate["fileId"],
        })
    assert exc.value.code == "DATA_CONFLICT"

    set_current_user(ADMIN)
    returned = payrolls.review(first["current"]["id"], {
        "action": "RETURN",
        "comment": "照片金额区域不清晰，请重新拍照上传",
        "expectedVersion": first["current"]["version"],
    }, ADMIN)
    assert returned["current"]["status"] == "RETURNED"

    set_current_user(STUDENT)
    photo_v2 = _image("2026-09工资凭证_v2.jpg", b"image-v2-payroll-corrected")
    corrected = payrolls.submit_my(STUDENT, {
        "batchId": str(batch_id), "internshipId": str(record_id),
        "payMonth": "2026-09",
        "actualAmount": "3300.00",
        "currency": "CNY",
        "paidOn": "2026-10-01",
        "evidenceFileId": photo_v2["fileId"],
        "correctionReason": "按老师要求重新拍摄清晰工资凭证",
        "submitNote": "更正版本",
    })
    assert corrected["revisionCount"] == 2
    assert corrected["current"]["revisionNo"] == 2
    assert corrected["current"]["actualAmount"] == 3300.0
    assert corrected["agreedSalary"] == 3500.0
    history = {item["revisionNo"]: item for item in corrected["history"]}
    assert history[1]["status"] == "SUPERSEDED"
    assert history[1]["actualAmount"] == 3200.0
    assert history[2]["status"] == "SUBMITTED"
    assert history[2]["evidenceSha256"] == photo_v2["sha256"]

    set_current_user(ADMIN)
    approved = payrolls.review(corrected["current"]["id"], {
        "action": "APPROVE",
        "comment": "金额与凭证核对一致",
        "expectedVersion": corrected["current"]["version"],
    }, ADMIN)
    assert approved["current"]["status"] == "APPROVED"
    assert approved["current"]["actualAmount"] == 3300.0
    assert approved["agreedSalary"] == 3500.0

    set_current_user(STUDENT)
    usd_photo = _image("2026-10工资凭证_USD.jpg", b"usd-payroll-image")
    usd = payrolls.submit_my(STUDENT, {
        "batchId": str(batch_id), "internshipId": str(record_id),
        "payMonth": "2026-10",
        "actualAmount": "500.00",
        "currency": "USD",
        "paidOn": "2026-10-31",
        "evidenceFileId": usd_photo["fileId"],
        "submitNote": "境外项目月度实发工资",
    })
    assert usd["current"]["currency"] == "USD"
    assert usd["agreedSalary"] == 3500.0
    assert usd["agreedSalaryCurrency"] == "CNY"

    with pytest.raises(AppException) as exc:
        outside_photo = _image("2027-03工资.jpg", b"outside-month")
        payrolls.submit_my(STUDENT, {
            "batchId": str(batch_id), "internshipId": str(record_id),
            "payMonth": "2027-03",
            "actualAmount": "1000",
            "currency": "CNY",
            "evidenceFileId": outside_photo["fileId"],
        })
    assert exc.value.code == "VALIDATION_ERROR"


def test_c05_routes_are_registered():
    from app.main import app
    paths = set(app.openapi().get("paths", {}))
    assert "/api/v1/mobile/internship/context/rotations" in paths
    assert "/api/v1/mobile/internship/context/rotations/{rotation_id}/self-evaluation" in paths
    assert "/api/v1/mobile/internship/context/payroll" in paths
    assert "/api/v1/mobile/teacher/internship/context/students/{record_id}/rotations" in paths
    assert "/api/v1/mobile/teacher/internship/context/rotations/{rotation_id}/evaluate" in paths
    assert "/api/v1/mobile/teacher/internship/context/payroll" in paths
    assert "/api/v1/mobile/teacher/internship/context/payroll/versions/{version_id}/review" in paths
