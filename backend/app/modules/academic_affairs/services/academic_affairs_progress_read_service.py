"""Module 02 read projection; transcript and program resolvers retain fact ownership."""
from sqlalchemy import func, or_, select

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException
from app.models import AcademicStudent, StudentProfile
from app.services import academic_service
from app.services.db_service import _tid, session
from .academic_affairs_grade_service import _transcript_page
from .student_program_resolution_service import credit_requirement_payload


def academic_progress(user, *, page=1, page_size=5, keyword=""):
    with session() as db:
        tenant = _tid()
        scope = build_affairs_context(user, db)
        condition = [AcademicStudent.tenant_id == tenant,
                     AcademicStudent.is_deleted.is_(False), AcademicStudent.record_status == "ACTIVE"]
        allowed = scope.allowed_class_ids(db)
        if scope.scope_type == "STUDENT":
            condition.append(AcademicStudent.student_id.in_(scope.student_ids | scope.psychology_student_ids))
        elif scope.scope_type == "SELF":
            condition.append(AcademicStudent.student_id == (scope.self_student_id or -1))
        elif allowed is not None:
            # The student master owns present class membership; legacy text cannot widen scope.
            condition.append(AcademicStudent.student_id.in_(select(StudentProfile.id).where(
                StudentProfile.tenant_id == tenant, StudentProfile.is_deleted.is_(False),
                StudentProfile.class_id.in_(allowed))))
        if keyword.strip():
            condition.append(or_(AcademicStudent.name.contains(keyword.strip(), autoescape=True),
                                 AcademicStudent.student_no.contains(keyword.strip(), autoescape=True)))
        total = int(db.scalar(select(func.count()).select_from(AcademicStudent).where(*condition)) or 0)
        records = db.scalars(select(AcademicStudent).where(*condition).order_by(AcademicStudent.id)
                             .offset((page - 1) * page_size).limit(page_size)).all()
        profiles = {r.id: r for r in db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant, StudentProfile.is_deleted.is_(False),
            StudentProfile.id.in_([r.student_id for r in records if r.student_id])))}
        items = []
        for record in records:
            profile = profiles.get(record.student_id)
            display = academic_service._stu_row(record, db=db, profiles=profiles, cache={})
            row = {key: display.get(key) for key in (
                "id", "studentId", "studentNo", "name", "className", "majorName", "grade", "counselor",
                "warningLevel", "warningLabel", "academicStatusLabel")}
            row.update(obtainedCredits=None, requiredCredits=None, gpa=None, sourceNote="学生来源尚未绑定")
            row["studentId"] = str(profile.id) if profile else None
            if profile is not None:
                try:
                    facts = _transcript_page(db, profile.id, 1, 1)
                    requirements = credit_requirement_payload(db, profile, tenant_id=tenant,
                                                              earned_credits=facts["earnedCredits"])
                    row.update(obtainedCredits=facts["earnedCredits"], requiredCredits=requirements["requiredCredits"],
                               gpa=facts["gpa"], programId=requirements["programId"],
                               sourceNote=requirements["blockingReason"] or "正式有效成绩与当前生效培养方案")
                except AppException as error:
                    if error.http_status != 409:
                        raise
                    row["sourceNote"] = "正式成绩来源存在冲突，请进入学生记录核对"
            items.append(row)
        return {"items": items, "total": total, "page": page, "pageSize": page_size}
