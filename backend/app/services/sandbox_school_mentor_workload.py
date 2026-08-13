"""20K 售前学校 · 导师角色池/实习导师/毕设导师统一编排与验收。"""
from __future__ import annotations

from sqlalchemy import func, select

from app.services.sandbox_school_graduation_mentor_reconcile import (
    reconcile_graduation_mentor_workload,
)
from app.services.sandbox_school_internship_mentor_reconcile import (
    reconcile_internship_mentor_workload,
)
from app.services.sandbox_school_mentor_pool import (
    EXPECTED_GRADUATION_MENTORS,
    EXPECTED_INTERNSHIP_MENTORS,
    MAX_GRADUATION_STUDENTS_PER_MENTOR,
    MAX_INTERNSHIP_STUDENTS_PER_MENTOR,
    ensure_role_and_advisor_scope,
    mentor_user_pools,
)


def _role_scope_counts(db, tenant_id: int, role_code: str) -> tuple[int, int]:
    from app.models import Role, TeacherStudentScope, UserRole

    role_id = db.scalar(select(Role.id).where(
        Role.tenant_id == tenant_id,
        Role.role_code == role_code,
        Role.status == "ACTIVE",
        Role.is_deleted.is_(False),
    ))
    if role_id is None:
        return 0, 0
    role_users = int(db.scalar(select(func.count(func.distinct(UserRole.user_id))).where(
        UserRole.tenant_id == tenant_id,
        UserRole.role_id == int(role_id),
        UserRole.status == "ACTIVE",
        UserRole.is_deleted.is_(False),
    )) or 0)
    scopes = int(db.scalar(select(func.count(func.distinct(TeacherStudentScope.teacher_key))).where(
        TeacherStudentScope.tenant_id == tenant_id,
        TeacherStudentScope.role_code == role_code,
        TeacherStudentScope.scope_type == "ADVISOR",
        TeacherStudentScope.status == "ACTIVE",
        TeacherStudentScope.is_deleted.is_(False),
    )) or 0)
    return role_users, scopes


def validate_school_mentor_workload_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AttendanceException,
        GraduationMentor,
        GraduationStudent,
        GraduationTopic,
        InternshipRecord,
        Major,
        RiskRecord,
        Role,
        TeacherStudentScope,
        User,
        UserRole,
        WeeklyReport,
    )
    from app.services.sandbox_school_role_reconcile import (
        EXPECTED_ORG_SCOPES,
        REQUIRED_ROLE_CODES,
        SECONDARY_ROLE_ASSIGNMENT_COUNTS,
    )

    intern_role_users, intern_scopes = _role_scope_counts(db, tenant_id, "INTERN_MENTOR")
    grad_role_users, grad_scopes = _role_scope_counts(db, tenant_id, "GD_MENTOR")

    intern_loads = [int(count) for (count,) in db.execute(select(func.count()).select_from(
        InternshipRecord
    ).where(
        InternshipRecord.tenant_id == tenant_id,
        InternshipRecord.advisor_user_id.is_not(None),
        InternshipRecord.is_deleted.is_(False),
    ).group_by(InternshipRecord.advisor_user_id)).all()]
    graduation_loads = [int(count) for (count,) in db.execute(select(func.count()).select_from(
        GraduationStudent
    ).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.mentor_id.is_not(None),
        GraduationStudent.is_deleted.is_(False),
    ).group_by(GraduationStudent.mentor_id)).all()]

    graduation_mentor_rows = int(db.scalar(select(func.count()).select_from(GraduationMentor).where(
        GraduationMentor.tenant_id == tenant_id,
        GraduationMentor.is_deleted.is_(False),
    )) or 0)
    graduation_current_sum = int(db.scalar(select(
        func.coalesce(func.sum(GraduationMentor.current_count), 0)
    ).where(
        GraduationMentor.tenant_id == tenant_id,
        GraduationMentor.is_deleted.is_(False),
    )) or 0)

    advisor_by_internship = {
        int(iid): advisor
        for iid, advisor in db.execute(select(
            InternshipRecord.id, InternshipRecord.advisor_name,
        ).where(
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.is_deleted.is_(False),
        )).all()
    }
    weekly_mismatch = sum(
        1
        for iid, reviewer in db.execute(select(
            WeeklyReport.internship_id, WeeklyReport.reviewed_by_name,
        ).where(
            WeeklyReport.tenant_id == tenant_id,
            WeeklyReport.reviewed_by_name.is_not(None),
            WeeklyReport.is_deleted.is_(False),
        )).all()
        if reviewer != advisor_by_internship[int(iid)]
    )
    exception_mismatch = sum(
        1
        for iid, handler in db.execute(select(
            AttendanceException.internship_id, AttendanceException.handled_by_name,
        ).where(
            AttendanceException.tenant_id == tenant_id,
            AttendanceException.handled_by_name.is_not(None),
            AttendanceException.is_deleted.is_(False),
        )).all()
        if handler != advisor_by_internship[int(iid)]
    )
    risk_mismatch = sum(
        1
        for iid, owner in db.execute(select(
            RiskRecord.internship_id, RiskRecord.owner_name,
        ).where(
            RiskRecord.tenant_id == tenant_id,
            RiskRecord.is_deleted.is_(False),
        )).all()
        if owner != advisor_by_internship[int(iid)]
    )

    mentor_major = {
        int(mid): major_name
        for mid, major_name in db.execute(select(
            GraduationMentor.id, GraduationMentor.major_name,
        ).where(
            GraduationMentor.tenant_id == tenant_id,
            GraduationMentor.is_deleted.is_(False),
        )).all()
    }
    major_name_by_id = {
        int(mid): major_name
        for mid, major_name in db.execute(select(Major.id, Major.major_name).where(
            Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False),
        )).all()
    }
    topic_major_mismatch = sum(
        1
        for mentor_id, major_name in db.execute(select(
            GraduationTopic.advisor_mentor_id, GraduationTopic.major_name,
        ).where(
            GraduationTopic.tenant_id == tenant_id,
            GraduationTopic.is_deleted.is_(False),
        )).all()
        if not mentor_id or mentor_major.get(int(mentor_id)) != major_name
    )
    student_major_mismatch = sum(
        1
        for mentor_id, major_id in db.execute(select(
            GraduationStudent.mentor_id, GraduationStudent.major_id,
        ).where(
            GraduationStudent.tenant_id == tenant_id,
            GraduationStudent.is_deleted.is_(False),
        )).all()
        if not mentor_id or mentor_major.get(int(mentor_id)) != major_name_by_id[int(major_id)]
    )

    # 非导师角色继续锁旧角色拓扑；导师角色由本模块扩为 224/384。
    role_id_by_code = {
        code: int(rid)
        for rid, code in db.execute(select(Role.id, Role.role_code).where(
            Role.tenant_id == tenant_id,
            Role.role_code.in_(REQUIRED_ROLE_CODES),
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
        )).all()
    }
    secondary_mismatches = {}
    for code, expected in SECONDARY_ROLE_ASSIGNMENT_COUNTS.items():
        rid = role_id_by_code.get(code)
        actual = 0 if rid is None else int(db.scalar(select(func.count()).select_from(UserRole).where(
            UserRole.tenant_id == tenant_id,
            UserRole.role_id == rid,
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
        )) or 0)
        if actual != expected:
            secondary_mismatches[code] = {"expected": expected, "actual": actual}

    non_mentor_scope_mismatches = {}
    for code, expected in EXPECTED_ORG_SCOPES.items():
        if code in {"INTERN_MENTOR", "GD_MENTOR"}:
            continue
        actual = int(db.scalar(select(func.count()).select_from(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == tenant_id,
            TeacherStudentScope.role_code == code,
            TeacherStudentScope.status == "ACTIVE",
            TeacherStudentScope.is_deleted.is_(False),
        )) or 0)
        if actual != expected:
            non_mentor_scope_mismatches[code] = {"expected": expected, "actual": actual}

    background_accounts = int(db.scalar(select(func.count()).select_from(User).where(
        User.tenant_id == tenant_id,
        User.login_name.like("sbx_%"),
        User.is_deleted.is_(False),
    )) or 0)

    report = {
        "internshipMentors": intern_role_users,
        "internshipAdvisorScopes": intern_scopes,
        "internshipMaxStudentsPerMentor": max(intern_loads, default=0),
        "graduationMentors": graduation_mentor_rows,
        "graduationRoleUsers": grad_role_users,
        "graduationAdvisorScopes": grad_scopes,
        "graduationMaxStudentsPerMentor": max(graduation_loads, default=0),
        "graduationCurrentCountSum": graduation_current_sum,
        "weeklyReviewerMismatches": weekly_mismatch,
        "exceptionHandlerMismatches": exception_mismatch,
        "riskOwnerMismatches": risk_mismatch,
        "graduationTopicMajorMismatches": topic_major_mismatch,
        "graduationStudentMajorMismatches": student_major_mismatch,
        "secondaryRoleMismatches": secondary_mismatches,
        "nonMentorScopeMismatches": non_mentor_scope_mismatches,
        "backgroundStaffAccounts": background_accounts,
    }
    expected = {
        "internshipMentors": EXPECTED_INTERNSHIP_MENTORS,
        "internshipAdvisorScopes": EXPECTED_INTERNSHIP_MENTORS,
        "graduationMentors": EXPECTED_GRADUATION_MENTORS,
        "graduationRoleUsers": EXPECTED_GRADUATION_MENTORS,
        "graduationAdvisorScopes": EXPECTED_GRADUATION_MENTORS,
        "graduationCurrentCountSum": 6400,
        "weeklyReviewerMismatches": 0,
        "exceptionHandlerMismatches": 0,
        "riskOwnerMismatches": 0,
        "graduationTopicMajorMismatches": 0,
        "graduationStudentMajorMismatches": 0,
        "backgroundStaffAccounts": 1280,
    }
    mismatches = {
        key: {"expected": value, "actual": report[key]}
        for key, value in expected.items()
        if report[key] != value
    }
    if report["internshipMaxStudentsPerMentor"] > MAX_INTERNSHIP_STUDENTS_PER_MENTOR:
        mismatches["internshipMaxStudentsPerMentor"] = {
            "max": MAX_INTERNSHIP_STUDENTS_PER_MENTOR,
            "actual": report["internshipMaxStudentsPerMentor"],
        }
    if report["graduationMaxStudentsPerMentor"] > MAX_GRADUATION_STUDENTS_PER_MENTOR:
        mismatches["graduationMaxStudentsPerMentor"] = {
            "max": MAX_GRADUATION_STUDENTS_PER_MENTOR,
            "actual": report["graduationMaxStudentsPerMentor"],
        }
    if secondary_mismatches or non_mentor_scope_mismatches:
        mismatches["roleTopology"] = {
            "secondary": secondary_mismatches,
            "nonMentorScopes": non_mentor_scope_mismatches,
        }
    if mismatches:
        raise RuntimeError(f"20K 导师工作量验收失败: {mismatches}")

    report["passed"] = True
    return report


def reconcile_school_mentor_workload_20k(db, tenant_id: int) -> dict:
    internship_users, graduation_users = mentor_user_pools(db, tenant_id)
    result = {
        "internshipRole": ensure_role_and_advisor_scope(
            db, tenant_id, "INTERN_MENTOR", internship_users
        ),
        "graduationRole": ensure_role_and_advisor_scope(
            db, tenant_id, "GD_MENTOR", graduation_users
        ),
        "internship": reconcile_internship_mentor_workload(db, tenant_id, internship_users),
        "graduation": reconcile_graduation_mentor_workload(db, tenant_id, graduation_users),
    }
    result["validation"] = validate_school_mentor_workload_20k(db, tenant_id)
    return result
