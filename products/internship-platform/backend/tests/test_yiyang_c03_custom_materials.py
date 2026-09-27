"""Yiyang C03 / G09: configurable material requirement, immutable resubmit and final archive source."""
from __future__ import annotations

from datetime import datetime

import pytest

TID = 1000000000000000001
ADMIN = {
    "tenantId": str(TID), "userId": "9001", "realName": "材料管理员",
    "userType": "SCHOOL_ADMIN", "currentRoleCode": "SCHOOL_ADMIN",
}
STUDENT = {
    "tenantId": str(TID), "userId": "2001", "studentId": "", "studentNo": "C03-001",
    "realName": "材料学生甲", "userType": "STUDENT", "currentRoleCode": "STUDENT",
}


@pytest.fixture()
def c03_db(tmp_path):
    import app.db.session as db_session
    from app.config import settings
    from app.models import (
        ArchiveManifest, ArchiveManifestItem, AuditOutbox, FileAsset, FileBinding, FileObject,
        FileVersion, InternshipAuditTrail, InternshipBatch, InternshipMaterialRequirement,
        InternshipMaterialSubmission, InternshipMaterialSubmissionFile,
        InternshipMaterialTemplateVersion, InternshipRecord, StudentProfile,
    )

    old_url = settings.DATABASE_URL
    old_storage = settings.FILE_STORAGE_ROOT
    settings.DATABASE_URL = f"sqlite+pysqlite:///{(tmp_path / 'c03.db').as_posix()}"
    settings.FILE_STORAGE_ROOT = str(tmp_path / "storage")
    db_session._engine = None
    db_session._factory = None
    engine = db_session.get_engine()

    for table in (
        InternshipBatch.__table__, StudentProfile.__table__, InternshipRecord.__table__,
        FileObject.__table__, FileAsset.__table__, FileVersion.__table__, FileBinding.__table__,
        ArchiveManifest.__table__, ArchiveManifestItem.__table__,
        InternshipMaterialRequirement.__table__, InternshipMaterialTemplateVersion.__table__,
        InternshipMaterialSubmission.__table__, InternshipMaterialSubmissionFile.__table__,
        InternshipAuditTrail.__table__, AuditOutbox.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    try:
        yield tmp_path
    finally:
        engine.dispose()
        settings.DATABASE_URL = old_url
        settings.FILE_STORAGE_ROOT = old_storage
        db_session._engine = None
        db_session._factory = None


def _seed():
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile

    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID, batch_name="益阳C03材料验收", batch_no="YIYANG-C03",
            start_date=datetime(2026, 9, 1), end_date=datetime(2027, 1, 31),
            planned_count=2, status="RUNNING",
        )
        db.add(batch); db.flush()
        records = []
        students = []
        for index in (1, 2):
            student = StudentProfile(
                tenant_id=TID, student_no=f"C03-{index:03d}", real_name=f"材料学生{'甲' if index == 1 else '乙'}",
                current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE",
            )
            db.add(student); db.flush()
            record = InternshipRecord(
                tenant_id=TID, student_id=student.id, batch_id=batch.id,
                advisor_name="", eligibility_status="QUALIFIED", destination_type="ASSIGNED",
                status="ONBOARD", risk_level="NONE",
                intern_start_date=datetime(2026, 9, 1), intern_end_date=datetime(2027, 1, 31),
            )
            db.add(record); db.flush()
            students.append(student.id); records.append(record.id)
        db.commit()
        return batch.id, students, records
    finally:
        db.close()


def _store(name: str, content: bytes, user: dict):
    from app.services import file_service
    return file_service.store_bytes(
        content, name, biz_type="TEMP_PRIVATE", user=user,
        visibility="PRIVATE", security_level="PERSONAL",
    )


def test_g09_custom_requirement_template_resubmit_missing_and_final_archive_source(c03_db):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import FileBinding, FileObject, FileVersion, InternshipMaterialSubmission
    from app.modules.internship.services import internship_material_requirement_service as svc

    set_tenant({"tenantId": str(TID)})
    set_current_user(ADMIN)
    batch_id, student_ids, record_ids = _seed()
    STUDENT["studentId"] = str(student_ids[0])

    requirement = svc.create_requirement({
        "batchId": str(batch_id),
        "materialCode": "ENTERPRISE_ACCEPTANCE",
        "materialName": "企业接收函",
        "description": "请下载学校模板，企业盖章后上传 PDF。",
        "isRequired": True,
        "audienceType": "ALL",
        "allowedExtensions": ["pdf"],
        "minFiles": 1,
        "maxFiles": 1,
        "dueAt": "2026-10-31T23:59:59",
    }, ADMIN)
    assert requirement["status"] == "DRAFT"
    assert requirement["materialName"] == "企业接收函"

    template_v1 = _store("企业接收函模板_v1.pdf", b"template-v1", ADMIN)
    with_template_v1 = svc.attach_template(requirement["id"], template_v1["fileId"], ADMIN)
    assert with_template_v1["template"]["versionNo"] == 1
    assert with_template_v1["template"]["sha256"] == template_v1["sha256"]

    template_v2 = _store("企业接收函模板_v2.pdf", b"template-v2-current", ADMIN)
    with_template_v2 = svc.attach_template(requirement["id"], template_v2["fileId"], ADMIN)
    assert with_template_v2["template"]["versionNo"] == 2
    assert with_template_v2["template"]["fileId"] == template_v2["fileId"]

    published = svc.publish_requirement(requirement["id"], ADMIN)
    assert published["status"] == "PUBLISHED"

    set_current_user(STUDENT)
    mine = svc.list_my_requirements(
        STUDENT, batch_id=batch_id, internship_id=record_ids[0])
    assert len(mine) == 1
    assert mine[0]["template"]["versionNo"] == 2
    assert mine[0]["template"]["sha256"] == template_v2["sha256"]

    # G09 safety gate: an infected upload may exist physically but cannot enter formal submission.
    infected = _store("infected.pdf", b"unsafe-payload", STUDENT)
    db = get_sessionmaker()()
    try:
        bad = db.get(FileObject, int(infected["fileId"]))
        bad.scan_status = "INFECTED"
        db.commit()
    finally:
        db.close()
    with pytest.raises(Exception):
        svc.submit_material(STUDENT, requirement["id"], {
            "batchId": str(batch_id), "internshipId": str(record_ids[0]),
            "fileIds": [infected["fileId"]],
        })

    student_v1 = _store("企业接收函_学生版_v1.pdf", b"student-version-one", STUDENT)
    submitted_v1 = svc.submit_material(STUDENT, requirement["id"], {
        "batchId": str(batch_id), "internshipId": str(record_ids[0]),
        "fileIds": [student_v1["fileId"]], "comment": "第一次提交",
    })
    assert submitted_v1["status"] == "SUBMITTED"
    assert submitted_v1["files"][0]["versionNo"] == 1

    set_current_user(ADMIN)
    returned = svc.review_submission(submitted_v1["id"], {
        "action": "RETURN", "comment": "企业盖章位置不清晰，请重新上传清晰扫描件",
        "expectedVersion": submitted_v1["version"],
    }, ADMIN)
    assert returned["status"] == "RETURNED"

    coverage = svc.coverage(requirement["id"], ADMIN)
    assert coverage["requiredStudents"] == 2
    assert coverage["effectiveSubmittedStudents"] == 0
    assert coverage["missingStudents"] == 2
    assert coverage["returnedStudents"] == 1

    missing_rows, missing_total = svc.list_students(
        requirement["id"], state="MISSING", page=1, page_size=20, user=ADMIN)
    assert missing_total == 2
    assert {row["studentNo"] for row in missing_rows} == {"C03-001", "C03-002"}

    set_current_user(STUDENT)
    student_v2 = _store("企业接收函_学生版_v2.pdf", b"student-version-two-final", STUDENT)
    submitted_v2 = svc.submit_material(STUDENT, requirement["id"], {
        "batchId": str(batch_id), "internshipId": str(record_ids[0]),
        "fileIds": [student_v2["fileId"]], "comment": "按退回意见重交",
    })
    assert submitted_v2["status"] == "SUBMITTED"
    assert submitted_v2["files"][0]["versionNo"] == 2
    assert submitted_v2["files"][0]["fileId"] == student_v2["fileId"]

    set_current_user(ADMIN)
    approved = svc.review_submission(submitted_v2["id"], {
        "action": "APPROVE", "comment": "盖章清晰，材料有效",
        "expectedVersion": submitted_v2["version"],
    }, ADMIN)
    assert approved["status"] == "APPROVED"
    assert approved["files"][0]["versionNo"] == 2

    db = get_sessionmaker()()
    try:
        submission = db.get(InternshipMaterialSubmission, int(approved["id"]))
        current = approved["files"][0]
        versions = db.query(FileVersion).filter_by(
            tenant_id=TID, asset_id=int(current["assetId"])
        ).order_by(FileVersion.version_no).all()
        assert [row.version_no for row in versions] == [1, 2]
        assert versions[0].is_current is False
        assert versions[0].status == "REJECTED"
        assert versions[1].is_current is True
        assert versions[1].status == "APPROVED"
        assert versions[1].file_object_id == int(student_v2["fileId"])

        old_bindings = db.query(FileBinding).filter_by(
            tenant_id=TID, asset_id=int(current["assetId"])
        ).order_by(FileBinding.version_no).all()
        assert len(old_bindings) == 2
        assert old_bindings[0].is_current is False
        assert old_bindings[0].status == "SUPERSEDED"
        assert old_bindings[1].is_current is True

        record = db.get(__import__("app.models", fromlist=["InternshipRecord"]).InternshipRecord, record_ids[0])
        sources = svc.approved_custom_sources(db, record)
        assert len(sources) == 1
        assert sources[0]["fileId"] == student_v2["fileId"]
        assert sources[0]["reviewStatus"] == "APPROVED"
        assert sources[0]["materialCode"] == "CUSTOM:ENTERPRISE_ACCEPTANCE:1"
        assert submission.status == "APPROVED"
    finally:
        db.close()

    final_coverage = svc.coverage(requirement["id"], ADMIN)
    assert final_coverage["requiredStudents"] == 2
    assert final_coverage["effectiveSubmittedStudents"] == 1
    assert final_coverage["approvedStudents"] == 1
    assert final_coverage["missingStudents"] == 1


def test_g09_routes_are_registered():
    from app.main import app
    paths = set(app.openapi().get("paths", {}))
    assert "/api/v1/internship/material-requirements" in paths
    assert "/api/v1/internship/material-requirements/{requirement_id}/template" in paths
    assert "/api/v1/internship/material-requirements/{requirement_id}/coverage" in paths
    assert "/api/v1/mobile/internship/context/material-requirements" in paths
    assert "/api/v1/mobile/internship/context/material-requirements/{requirement_id}/submit" in paths
    assert "/api/v1/mobile/teacher/internship/context/material-requirements" in paths
    assert "/api/v1/mobile/teacher/internship/context/material-submissions/{submission_id}/review" in paths
