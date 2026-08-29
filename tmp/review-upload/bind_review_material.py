"""Bind the uploaded demo DOCX as append-only canonical evidence for legacy final 23."""
from app.core.context import set_current_user, set_tenant
from app.models import GraduationStudent
from app.modules.graduation.materials.command_service import adopt_legacy_file_in_session
from app.modules.graduation.materials.rule_service import initialize_default_rule_in_session
from app.services.db_service import session


TENANT_ID = 1000000000000000004
GD_STUDENT_ID = 69
FINAL_ID = 23
FILE_ID = 17


student_user = {
    "id": "62",
    "userId": "62",
    "tenantId": str(TENANT_ID),
    "loginName": "E2E20260001",
    "realName": "E2E学生A",
    "userType": "STUDENT",
    "currentRoleCode": "STUDENT",
    "studentId": "369",
    "studentNo": "E2E20260001",
    "graduationBatchId": "32",
    "allowedBatchIds": ["32"],
    "allowedStudentIds": ["369"],
    "allowedStudentNos": ["E2E20260001"],
}


set_tenant(TENANT_ID)
set_current_user(student_user)

with session() as db:
    initialize_default_rule_in_session(db, 32, student_user)
    student = db.get(GraduationStudent, GD_STUDENT_ID)
    if student is None:
        raise RuntimeError("graduation student 69 was not found")
    result = adopt_legacy_file_in_session(
        db,
        student,
        "THESIS_FINAL",
        FILE_ID,
        source_record_type="FINAL",
        source_record_id=str(FINAL_ID),
        user=student_user,
        approved=True,
        binding_metadata={
            "purpose": "interactive review demo",
            "uploadedByRequest": True,
            "legacyFinalId": str(FINAL_ID),
        },
    )
    db.commit()
    print(result)
