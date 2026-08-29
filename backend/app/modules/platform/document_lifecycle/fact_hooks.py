"""Small, explicit C4 domain-to-fact mappings used by canonical transactions."""
from __future__ import annotations

from datetime import datetime

from app.modules.platform.document_lifecycle.lifecycle_fact_writer import (
    LifecycleFactInput,
    record_in_session,
)


def academic_status_effective(db, *, student, academic_fact_version: int,
                              event_time: datetime, change_type: str, actor_id: int | None):
    return record_in_session(db, LifecycleFactInput(
        student_id=int(student.id), college_id=student.college_id,
        source_module="academic-affairs", fact_type="ACADEMIC_STATUS_EFFECTIVE",
        source_biz_type="STUDENT_ACADEMIC_FACT", source_biz_id=str(student.id),
        source_version=str(academic_fact_version), event_time=event_time,
        title="学籍状态已生效", summary=None, importance="HIGH",
        visibility_code="STUDENT_SELF_AND_SCOPED_STAFF", sensitivity_level="PERSONAL",
        target_ref={"type": "ACADEMIC_STUDENT_STATUS", "id": str(student.id), "action": "VIEW"},
        metadata={"changeType": str(change_type)}, created_by=actor_id,
    ))


def graduation_archived(db, *, student, manifest, actor_id: int | None):
    return record_in_session(db, LifecycleFactInput(
        student_id=int(student.student_id), college_id=student.college_id,
        source_module="graduation", fact_type="GRADUATION_ARCHIVED",
        source_biz_type="ARCHIVE_MANIFEST", source_biz_id=str(manifest.id),
        source_version=str(manifest.revision), event_time=manifest.frozen_at or datetime.utcnow(),
        title="毕业设计已归档", summary=None, importance="HIGH",
        visibility_code="STUDENT_SELF_AND_SCOPED_STAFF", sensitivity_level="PERSONAL",
        target_ref={"type": "GRADUATION_STUDENT", "id": str(student.id), "action": "VIEW"},
        created_by=actor_id,
    ))


def internship_completed(db, *, record, archive, source_version: int, actor_id: int | None):
    return record_in_session(db, LifecycleFactInput(
        student_id=int(record.student_id), college_id=None,
        source_module="internship", fact_type="INTERNSHIP_COMPLETED",
        source_biz_type="INTERNSHIP_ARCHIVE", source_biz_id=str(archive.id),
        source_version=str(source_version), event_time=archive.archived_at or datetime.utcnow(),
        title="岗位实习已归档", summary=None, importance="HIGH",
        visibility_code="STUDENT_SELF_AND_SCOPED_STAFF", sensitivity_level="PERSONAL",
        target_ref={"type": "INTERNSHIP_RECORD", "id": str(record.id), "action": "VIEW"},
        created_by=actor_id,
    ))


def employment_verified(db, *, student, actor_id: int | None):
    student_id = getattr(student, "student_id", None)
    if not student_id:
        from sqlalchemy import select
        from app.models.student import StudentProfile
        profile = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == int(student.tenant_id),
            StudentProfile.student_no == str(student.student_no),
            StudentProfile.is_deleted.is_(False),
        ).limit(1)).first()
        if profile is None:
            # The selected first-scope hook requires a canonical StudentProfile identity.
            # Fail closed in the same transaction instead of inventing a parallel student id.
            from app.core.exceptions import AppException
            raise AppException("DATA_CONFLICT", "就业记录缺少可解析的学生主档身份")
        student_id = profile.id
    return record_in_session(db, LifecycleFactInput(
        student_id=int(student_id), college_id=None,
        source_module="employment", fact_type="EMPLOYMENT_VERIFIED",
        source_biz_type="EMP_STUDENT", source_biz_id=str(student.id),
        source_version=str(student.version), event_time=datetime.utcnow(),
        title="就业去向已核验", summary=None, importance="HIGH",
        visibility_code="STUDENT_SELF_AND_SCOPED_STAFF", sensitivity_level="PERSONAL",
        target_ref={"type": "EMPLOYMENT_STUDENT", "id": str(student.id), "action": "VIEW"},
        created_by=actor_id,
    ))


def affairs_leave_approved(db, *, leave, actor_id: int | None):
    return record_in_session(db, LifecycleFactInput(
        student_id=int(leave.student_id), college_id=None,
        source_module="student-affairs", fact_type="AFFAIRS_LEAVE_APPROVED",
        source_biz_type="AFFAIRS_LEAVE", source_biz_id=str(leave.id),
        source_version=str(leave.version), event_time=datetime.utcnow(),
        title="请假审批已通过", summary=None, importance="NORMAL",
        visibility_code="STUDENT_SELF_AND_SCOPED_STAFF", sensitivity_level="PERSONAL",
        target_ref={"type": "AFFAIRS_LEAVE", "id": str(leave.id), "action": "VIEW"},
        created_by=actor_id,
    ))
