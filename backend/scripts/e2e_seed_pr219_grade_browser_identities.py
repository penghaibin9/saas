"""Test-only identity prerequisite for PR219 grade Browser-First acceptance.

Direct DB setup is limited to disposable identity/org prerequisites. GradeTask, scores,
review, publish, transcript visibility and correction writes remain browser/API writes.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import College, Major, Role, SchoolClass, StudentProfile, TeacherStudentScope, Tenant, User, UserRole

TENANT_CODE = "sandbox-school"
PASSWORD = "E2eTest@2026"
COLLEGE_NAME = "E2E教务测试学院A"
MAJOR_NAME = "E2E教务测试软件技术"
CLASS_NAME = "E2E教务测试软技2601班"

STAFF = (
    ("e2e_aa_teacher_a", "E2E教务测试任课教师A", "ACADEMIC_TEACHER", "TEACHER"),
    ("e2e_aa_teacher_b", "E2E教务测试任课教师B", "ACADEMIC_TEACHER", "TEACHER"),
    ("e2e_aa_college_a", "E2E教务测试学院教务老师A", "COLLEGE_ADMIN", "TEACHER"),
    ("e2e_aa_grade", "E2E教务测试成绩审核发布", "ACADEMIC_ADMIN", "ADMIN"),
)
STUDENTS = (
    ("E2EAA20260001", "E2E教务测试学生A", "男"),
    ("E2EAA20260002", "E2E教务测试学生B", "女"),
)


def _safe() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    if str(os.getenv("APP_ENV") or "").lower() in {"prod", "production"}:
        raise SystemExit("refusing PR219 grade identity seed in production")
    url = str(os.getenv("DATABASE_URL") or "")
    low = url.lower()
    if not url or not any(x in low for x in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must be disposable e2e/test")
    if any(x in low for x in ("prod", "production", "staging")):
        raise SystemExit("DATABASE_URL looks non-disposable")
    if urlparse(url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("only local DB is accepted")


def _one(db, model, *criteria):
    return db.scalars(select(model).where(*criteria)).first()


def _role(db, tid: int, code: str) -> Role:
    row = _one(db, Role, Role.tenant_id == tid, Role.role_code == code, Role.is_deleted.is_(False))
    if row is None:
        row = Role(
            tenant_id=tid,
            role_code=code,
            role_name=code,
            role_type="SYSTEM",
            status="ACTIVE",
        )
        db.add(row)
        db.flush()
    else:
        row.role_type = "SYSTEM"
        row.status = "ACTIVE"
        row.is_deleted = False
    return row


def _user(db, tid: int, login: str, name: str, role_code: str, user_type: str) -> User:
    row = _one(db, User, User.tenant_id == tid, User.login_name == login)
    if row is None:
        row = User(
            tenant_id=tid,
            login_name=login,
            real_name=name,
            password_hash=hash_password(PASSWORD),
            user_type=user_type,
            status="ACTIVE",
            must_change_password=False,
        )
        db.add(row)
    else:
        row.real_name = name
        row.password_hash = hash_password(PASSWORD)
        row.user_type = user_type
        row.status = "ACTIVE"
        row.must_change_password = False
        row.is_deleted = False
    db.flush()
    role = _role(db, tid, role_code)
    link = _one(
        db, UserRole,
        UserRole.tenant_id == tid,
        UserRole.user_id == row.id,
        UserRole.role_id == role.id,
        UserRole.is_deleted.is_(False),
    )
    if link is None:
        db.add(UserRole(tenant_id=tid, user_id=row.id, role_id=role.id, status="ACTIVE"))
    else:
        link.status = "ACTIVE"
        link.is_deleted = False
    return row


def _scope(db, tid: int, user: User, role_code: str, college_name: str) -> None:
    row = _one(
        db, TeacherStudentScope,
        TeacherStudentScope.tenant_id == tid,
        TeacherStudentScope.teacher_key == user.login_name,
        TeacherStudentScope.role_code == role_code,
        TeacherStudentScope.scope_type == "COLLEGE",
        TeacherStudentScope.ref_value == college_name,
        TeacherStudentScope.is_deleted.is_(False),
    )
    if row is None:
        db.add(TeacherStudentScope(
            tenant_id=tid,
            teacher_key=user.login_name,
            teacher_name=user.real_name,
            role_code=role_code,
            scope_type="COLLEGE",
            ref_value=college_name,
            status="ACTIVE",
        ))
    else:
        row.teacher_name = user.real_name
        row.status = "ACTIVE"
        row.is_deleted = False


def main() -> int:
    _safe()
    db = get_sessionmaker()()
    try:
        tenant = _one(db, Tenant, Tenant.tenant_code == TENANT_CODE, Tenant.is_deleted.is_(False))
        if tenant is None:
            raise SystemExit("sandbox-school missing; run Playwright tenant seed first")
        tid = int(tenant.id)

        users = {login: _user(db, tid, login, name, role, user_type)
                 for login, name, role, user_type in STAFF}

        college = _one(db, College, College.tenant_id == tid, College.college_name == COLLEGE_NAME,
                       College.is_deleted.is_(False))
        if college is None:
            college = College(
                tenant_id=tid,
                college_name=COLLEGE_NAME,
                code="E2E-AA-COL-A",
                short_name="E2E教务A",
                status="ACTIVE",
            )
            db.add(college)
            db.flush()
        college.status = "ACTIVE"
        college.is_deleted = False
        college.secretary_id = int(users["e2e_aa_college_a"].id)

        major = _one(db, Major, Major.tenant_id == tid, Major.major_name == MAJOR_NAME,
                     Major.is_deleted.is_(False))
        if major is None:
            major = Major(
                tenant_id=tid,
                college_id=college.id,
                major_name=MAJOR_NAME,
                code="E2E-AA-MAJ-A",
                status="ACTIVE",
                enroll_status="ENROLLING",
            )
            db.add(major)
            db.flush()
        major.college_id = college.id
        major.status = "ACTIVE"
        major.is_deleted = False

        school_class = _one(db, SchoolClass, SchoolClass.tenant_id == tid,
                            SchoolClass.class_name == CLASS_NAME, SchoolClass.is_deleted.is_(False))
        if school_class is None:
            school_class = SchoolClass(
                tenant_id=tid,
                major_id=major.id,
                class_name=CLASS_NAME,
                class_code="E2E-AA-CLS-A1",
                grade="2026",
                capacity=40,
                class_status="NORMAL",
                status="ACTIVE",
            )
            db.add(school_class)
            db.flush()
        school_class.major_id = major.id
        school_class.status = "ACTIVE"
        school_class.class_status = "NORMAL"
        school_class.is_deleted = False

        for login in ("e2e_aa_teacher_a", "e2e_aa_teacher_b"):
            _scope(db, tid, users[login], "ACADEMIC_TEACHER", COLLEGE_NAME)
        _scope(db, tid, users["e2e_aa_college_a"], "COLLEGE_ADMIN", COLLEGE_NAME)

        for student_no, name, gender in STUDENTS:
            _user(db, tid, student_no, name, "STUDENT", "STUDENT")
            student = _one(db, StudentProfile, StudentProfile.tenant_id == tid,
                           StudentProfile.student_no == student_no)
            if student is None:
                student = StudentProfile(
                    tenant_id=tid,
                    student_no=student_no,
                    real_name=name,
                    gender=gender,
                    college_id=college.id,
                    major_id=major.id,
                    class_id=school_class.id,
                    grade="2026",
                    current_stage="ON_CAMPUS",
                    student_status="REGISTERED",
                    status="ACTIVE",
                )
                db.add(student)
            else:
                student.real_name = name
                student.gender = gender
                student.college_id = college.id
                student.major_id = major.id
                student.class_id = school_class.id
                student.grade = "2026"
                student.current_stage = "ON_CAMPUS"
                student.student_status = "REGISTERED"
                student.status = "ACTIVE"
                student.is_deleted = False

        db.commit()
        print({
            "tenant": TENANT_CODE,
            "collegeId": int(college.id),
            "majorId": int(major.id),
            "classId": int(school_class.id),
            "staff": sorted(users),
            "students": [x[0] for x in STUDENTS],
        })
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
