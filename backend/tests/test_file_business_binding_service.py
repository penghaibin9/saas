"""包 6：业务文件绑定门面必须在调用方事务内 fail-closed。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

TID = 1000000000000000001


def _seed(db):
    from app.models import InternshipBatch, InternshipRecord, StudentProfile, Tenant
    from app.models.file import FileObject

    if db.get(Tenant, TID) is None:
        db.add(Tenant(
            id=TID,
            tenant_code="demo",
            school_name="文件绑定测试学校",
            short_name="文件绑定测试",
            deploy_mode="SAAS",
            db_mode="SHARED",
            status="ACTIVE",
        ))
        db.flush()
    batch = db.scalar(select(InternshipBatch).where(
        InternshipBatch.tenant_id == TID,
        InternshipBatch.batch_no == "FILE-BIND-BATCH",
        InternshipBatch.is_deleted.is_(False),
    ))
    if batch is None:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="文件绑定测试批次",
            batch_no="FILE-BIND-BATCH",
            status="RUNNING",
        )
        db.add(batch)
        db.flush()
    student = StudentProfile(
        tenant_id=TID,
        student_no="FILE-BIND-001",
        real_name="文件绑定学生",
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
        advisor_user_id=9001,
        advisor_name="文件绑定老师",
        status="PREPARING",
        eligibility_status="QUALIFIED",
        destination_type="NONE",
        risk_level="NONE",
    )
    db.add(record)
    file_obj = FileObject(
        tenant_id=TID,
        file_key="binding/temp.pdf",
        file_name="temp.pdf",
        ext="pdf",
        mime_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
        biz_type="TEMP_PRIVATE",
        biz_id=None,
        owner_user_id=9001,
        visibility="PRIVATE",
        status="AVAILABLE",
        storage_backend="local",
        storage_zone="ACTIVE",
        upload_source="USER",
        scan_required=False,
        scan_status="NOT_REQUIRED",
    )
    db.add(file_obj)
    db.flush()
    return student, record, file_obj


def test_bind_file_to_authoritative_business_in_same_transaction(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models.file import FileBinding, FileObject
    from app.services.file_business_binding_service import bind_file_to_business

    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    actor = {
        "userId": "9001",
        "realName": "文件绑定老师",
        "userType": "TEACHER",
        "tenantId": str(TID),
        "currentRoleCode": "TEACHER",
    }
    set_current_user(actor)
    db = get_sessionmaker()()
    try:
        student, record, file_obj = _seed(db)
        binding = bind_file_to_business(
            db,
            file_id=file_obj.id,
            biz_type="INTERNSHIP_INSURANCE",
            biz_id="77",
            actor=actor,
            subject_type="STUDENT",
            subject_id=str(student.id),
            module_code="INTERNSHIP",
            student_id=student.id,
            scope={"internshipId": str(record.id), "studentId": str(student.id)},
        )
        db.commit()
        row = db.get(FileObject, file_obj.id)
        persisted = db.scalar(select(FileBinding).where(FileBinding.id == binding.id))
        assert row.biz_type == "INTERNSHIP_INSURANCE"
        assert row.biz_id == "77"
        assert row.visibility == "BIZ_SCOPED"
        assert persisted is not None
        assert persisted.status == "ACTIVE"
        assert persisted.subject_type == "STUDENT"
        assert persisted.subject_id == str(student.id)
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


def test_scan_pending_file_cannot_become_formal_binding(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models.file import FileBinding
    from app.services.file_business_binding_service import bind_file_to_business

    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    actor = {"userId": "9001", "realName": "文件绑定老师", "userType": "TEACHER"}
    set_current_user(actor)
    db = get_sessionmaker()()
    try:
        student, record, file_obj = _seed(db)
        file_obj.status = "QUARANTINED"
        file_obj.scan_required = True
        file_obj.scan_status = "PENDING"
        with pytest.raises(AppException) as exc:
            bind_file_to_business(
                db,
                file_id=file_obj.id,
                biz_type="INTERNSHIP_INSURANCE",
                biz_id="88",
                actor=actor,
                subject_type="STUDENT",
                subject_id=str(student.id),
                module_code="INTERNSHIP",
                student_id=student.id,
                scope={"internshipId": str(record.id), "studentId": str(student.id)},
            )
        assert exc.value.code == "FILE_NOT_READY"
        db.rollback()
        assert db.scalars(select(FileBinding).where(FileBinding.file_id == file_obj.id)).all() == []
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


def test_existing_binding_cannot_be_retargeted(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.services.file_business_binding_service import bind_file_to_business

    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    actor = {"userId": "9001", "realName": "文件绑定老师", "userType": "TEACHER"}
    set_current_user(actor)
    db = get_sessionmaker()()
    try:
        student, record, file_obj = _seed(db)
        bind_file_to_business(
            db,
            file_id=file_obj.id,
            biz_type="INTERNSHIP_INSURANCE",
            biz_id="99",
            actor=actor,
            subject_type="STUDENT",
            subject_id=str(student.id),
            module_code="INTERNSHIP",
            student_id=student.id,
            scope={"internshipId": str(record.id), "studentId": str(student.id)},
        )
        db.flush()
        with pytest.raises(AppException) as exc:
            bind_file_to_business(
                db,
                file_id=file_obj.id,
                biz_type="INTERNSHIP_AGREEMENT",
                biz_id="100",
                actor=actor,
                subject_type="STUDENT",
                subject_id=str(student.id),
                module_code="INTERNSHIP",
                student_id=student.id,
                scope={"internshipId": str(record.id), "studentId": str(student.id)},
            )
        assert exc.value.code == "FILE_ALREADY_BOUND"
        db.rollback()
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)
