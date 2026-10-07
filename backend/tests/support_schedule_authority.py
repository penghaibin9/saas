"""Explicit, idempotent MySQL facts for scheduling prerequisites; no guard bypasses."""
from datetime import datetime

TID = 1000000000000000001


def seed_school_schedule_operator(db):
    from app.models import Role, RoleAssignmentScope, RolePermission, UserRole
    from tests.support_academic_review_identity import _ensure_review_assignment
    from tests.support_grade_review_identity import _ensure_account, _ensure_permission
    user = _ensure_account(db, "school_admin01")
    role = db.query(Role).filter(Role.tenant_id == TID,
        Role.role_code == "TEST_GRADE_SCHOOL_ADMIN01").one()
    for code in ("academicAffairs.schedule.view", "academicAffairs.schedule.edit",
                 "academicAffairs.schedule.publish", "academicAffairs.schedule.archive"):
        permission = _ensure_permission(db, code)
        if not db.query(RolePermission).filter(RolePermission.tenant_id == TID,
                RolePermission.role_id == role.id, RolePermission.permission_id == permission.id).first():
            db.add(RolePermission(tenant_id=TID, role_id=role.id,
                permission_id=permission.id, status="ACTIVE"))
    member = db.query(UserRole).filter(UserRole.tenant_id == TID,
        UserRole.user_id == user.id, UserRole.role_id == role.id).one()
    if not db.query(RoleAssignmentScope).filter(RoleAssignmentScope.tenant_id == TID,
            RoleAssignmentScope.user_role_id == member.id,
            RoleAssignmentScope.scope_type == "SCHOOL").first():
        db.add(RoleAssignmentScope(tenant_id=TID, user_id=user.id, user_role_id=member.id,
            role_code=role.role_code, scope_type="SCHOOL", scope_id=TID,
            effective_at=datetime(2020, 1, 1), status="ACTIVE"))
    _ensure_review_assignment(db, user_id=user.id, org_type="SCHOOL", org_id=TID,
        assignment_type="ACADEMIC_REVIEWER")
    db.flush()
    return user


def seed_schedule_program_source(db, task):
    """Attach a READY scenario task to its actual course, class, cohort and program."""
    from app.models import (AaCourse, AaProgram, AaProgramBinding, AaProgramCourse,
        AaTeachingTaskBatch, AaTerm, College, Major, SchoolClass, User, Role, UserRole)
    batch = db.get(AaTeachingTaskBatch, task.batch_id)
    term = db.get(AaTerm, batch.term_id)
    college = db.get(College, batch.college_id)
    course = db.get(AaCourse, task.course_id)
    assert all(x is not None and x.tenant_id == TID for x in (batch, term, college, course))
    assert college.status == "ACTIVE"
    if course.owner_college_id is None:
        course.owner_college_id = college.id
    assert course.owner_college_id == college.id
    cohort = str(term.year_code).split("-")[0]
    klass = db.get(SchoolClass, task.class_id) if task.class_id else None
    if klass is None:
        major = Major(tenant_id=TID, college_id=college.id,
            major_name=f"排课来源专业-{course.id}", status="ACTIVE")
        db.add(major); db.flush()
        klass = SchoolClass(tenant_id=TID, major_id=major.id, grade=cohort,
            class_name=f"排课来源班-{course.id}", status="ACTIVE", class_status="NORMAL")
        db.add(klass); db.flush()
        task.class_id = klass.id
    major = db.get(Major, klass.major_id)
    assert major is not None and major.tenant_id == TID
    if not task.teaching_class_name:
        task.teaching_class_name = klass.class_name
    program_name = f"排课来源方案-{klass.id}"
    program = db.query(AaProgram).filter(AaProgram.tenant_id == TID,
        AaProgram.program_name == program_name, AaProgram.is_deleted.is_(False)).first()
    if program is None:
        program = AaProgram(tenant_id=TID, major_id=major.id, grade_year=klass.grade,
            program_name=program_name, total_credits=0, status="PUBLISHED")
        db.add(program); db.flush()
        db.add(AaProgramBinding(tenant_id=TID, program_id=program.id,
            major_id=major.id, class_id=klass.id, grade_year=klass.grade,
            bound_at=datetime(2020, 1, 1), status="ACTIVE"))
    planned = db.query(AaProgramCourse).filter(AaProgramCourse.tenant_id == TID,
        AaProgramCourse.program_id == program.id, AaProgramCourse.course_id == course.id,
        AaProgramCourse.is_deleted.is_(False)).first()
    if planned is None:
        planned = AaProgramCourse(tenant_id=TID, program_id=program.id, course_id=course.id,
            course_name=course.course_name, credit_snapshot=course.credit,
            open_term_no=(int(cohort) - int(klass.grade)) * 2 + int(term.term_no),
            module="MAJOR_CORE", formation_mode="ADMIN_FIXED")
        db.add(planned); db.flush()
        program.total_credits = float(program.total_credits or 0) + float(course.credit or 0)
    task.source_program_course_id = planned.id
    task.formation_mode = "ADMIN_FIXED"
    if not task.total_hours:
        task.total_hours = int(task.weekly_hours) * (int(task.end_week) - int(task.start_week) + 1)
    if not course.hours_total:
        course.hours_total = task.total_hours
        course.hours_theory = task.total_hours
    teacher = db.query(User).filter(User.tenant_id == TID, User.login_name == task.teacher_key).first()
    if teacher is None:
        teacher = User(tenant_id=TID, login_name=task.teacher_key,
            real_name=task.teacher_name, user_type="TEACHER", password_hash="x", status="ACTIVE")
        db.add(teacher); db.flush()
        role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == "ACADEMIC_TEACHER").first()
        if role is None:
            role = Role(tenant_id=TID, role_code="ACADEMIC_TEACHER", role_name="任课教师", status="ACTIVE")
            db.add(role); db.flush()
        db.add(UserRole(tenant_id=TID, user_id=teacher.id, role_id=role.id, status="ACTIVE"))
    db.flush()
    return planned
