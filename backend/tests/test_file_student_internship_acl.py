"""包 6：学生实习文件必须解析到稳定 studentId，不能依赖客户端批次头。"""
from __future__ import annotations

TID = 1000000000000000001


def test_student_without_batch_header_can_only_read_own_bound_internship_file(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile, Tenant
    from app.models.file import FileObject
    from app.services.file_business_binding_service import bind_file_to_business
    from app.services.file_public_acl_guard import strict_scoped_binding_resolver

    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    teacher = {
        "userId": "9001",
        "realName": "文件绑定老师",
        "userType": "TEACHER",
        "tenantId": str(TID),
        "currentRoleCode": "TEACHER",
    }
    set_current_user(teacher)
    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(
                id=TID,
                tenant_code="demo",
                school_name="文件学生范围测试学校",
                short_name="文件学生范围测试",
                deploy_mode="SAAS",
                db_mode="SHARED",
                status="ACTIVE",
            ))
            db.flush()
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="文件学生范围测试批次",
            batch_no="FILE-STUDENT-ACL-BATCH",
            status="RUNNING",
        )
        db.add(batch)
        db.flush()
        student = StudentProfile(
            tenant_id=TID,
            student_no="FILE-STUDENT-ACL-001",
            real_name="本人学生",
            current_stage="INTERNSHIP",
            student_status="NORMAL",
            status="ACTIVE",
        )
        other = StudentProfile(
            tenant_id=TID,
            student_no="FILE-STUDENT-ACL-002",
            real_name="其他学生",
            current_stage="INTERNSHIP",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add_all([student, other])
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
            file_key="binding/student-acl.pdf",
            file_name="student-acl.pdf",
            ext="pdf",
            mime_type="application/pdf",
            size_bytes=10,
            sha256="b" * 64,
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
        binding = bind_file_to_business(
            db,
            file_id=file_obj.id,
            biz_type="INTERNSHIP_APPLICATION",
            biz_id="501",
            actor=teacher,
            subject_type="STUDENT",
            subject_id=str(student.id),
            module_code="INTERNSHIP",
            student_id=student.id,
            scope={
                "internshipId": str(record.id),
                "studentId": str(student.id),
                "studentNo": student.student_no,
                "businessType": "INTERNSHIP_APPLICATION",
                "businessId": "501",
            },
        )
        db.flush()
        assert strict_scoped_binding_resolver(
            db,
            file_obj,
            [binding],
            {"userType": "STUDENT", "studentNo": student.student_no},
            "meta",
        ) is True
        assert strict_scoped_binding_resolver(
            db,
            file_obj,
            [binding],
            {"userType": "STUDENT", "studentNo": other.student_no},
            "meta",
        ) is False
        db.rollback()
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)
