#!/usr/bin/env python3
"""Seed the minimal real MySQL facts used by standalone full-stack PC browser evidence."""
from __future__ import annotations

from sqlalchemy import delete

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import (
    InternshipBatch,
    Role,
    StudentAccountLink,
    StudentProfile,
    Tenant,
    User,
    UserRole,
)

TENANT_ID = 88101
STAFF_ID = 88111
STUDENT_ID = 88112
STAFF_ROLE_ID = 88121
STUDENT_ROLE_ID = 88122
MENTOR_ROLE_ID = 88123
MENTOR_ID = 88113
STUDENT_PROFILE_ID = 88131
BATCH_ID = 88141


def seed() -> None:
    db = get_sessionmaker()()
    try:
        db.execute(delete(InternshipBatch).where(InternshipBatch.tenant_id == TENANT_ID))
        db.execute(delete(StudentAccountLink).where(StudentAccountLink.tenant_id == TENANT_ID))
        db.execute(delete(StudentProfile).where(StudentProfile.tenant_id == TENANT_ID))
        db.execute(delete(UserRole).where(UserRole.tenant_id == TENANT_ID))
        db.execute(delete(Role).where(Role.tenant_id == TENANT_ID))
        db.execute(delete(User).where(User.tenant_id == TENANT_ID))
        db.execute(delete(Tenant).where(Tenant.id == TENANT_ID))
        db.commit()

        db.add(Tenant(
            id=TENANT_ID,
            tenant_code="YIYANG-FULLSTACK",
            school_name="益阳职业技术学院",
            short_name="益阳职院",
            deploy_mode="SAAS",
            db_mode="SHARED",
            status="ACTIVE",
        ))
        db.add_all([
            Role(
                id=STAFF_ROLE_ID,
                tenant_id=TENANT_ID,
                role_code="SCHOOL_ADMIN",
                role_name="学校管理员",
                role_type="SYSTEM",
                status="ACTIVE",
            ),
            Role(
                id=MENTOR_ROLE_ID,
                tenant_id=TENANT_ID,
                role_code="INTERN_MENTOR",
                role_name="实习指导教师",
                role_type="SYSTEM",
                status="ACTIVE",
            ),
            Role(
                id=STUDENT_ROLE_ID,
                tenant_id=TENANT_ID,
                role_code="STUDENT",
                role_name="学生",
                role_type="SYSTEM",
                status="ACTIVE",
            ),
            User(
                id=STAFF_ID,
                tenant_id=TENANT_ID,
                login_name="yiyang.fullstack.admin",
                real_name="益阳实习管理员",
                password_hash=hash_password("Fullstack-Admin-2026!"),
                user_type="SCHOOL_ADMIN",
                status="ACTIVE",
                must_change_password=False,
                credential_version=0,
            ),
            User(
                id=MENTOR_ID,
                tenant_id=TENANT_ID,
                login_name="yiyang.fullstack.mentor",
                real_name="李指导老师",
                password_hash=hash_password("Fullstack-Mentor-2026!"),
                user_type="TEACHER",
                status="ACTIVE",
                must_change_password=False,
                credential_version=0,
            ),
            User(
                id=STUDENT_ID,
                tenant_id=TENANT_ID,
                login_name="202688013",
                real_name="学生李明",
                password_hash=hash_password("Fullstack-Student-2026!"),
                user_type="STUDENT",
                status="ACTIVE",
                must_change_password=False,
                credential_version=0,
            ),
            StudentProfile(
                id=STUDENT_PROFILE_ID,
                tenant_id=TENANT_ID,
                student_no="202688013",
                real_name="学生李明",
                current_stage="ENROLLED",
                student_status="NORMAL",
                status="ACTIVE",
            ),
            InternshipBatch(
                id=BATCH_ID,
                tenant_id=TENANT_ID,
                batch_name="2026岗位实习",
                batch_no="YIYANG-2026-FULLSTACK",
                academic_year="2026-2027",
                term="1",
                planned_count=1,
                status="RUNNING",
                archive_status="NOT_ARCHIVED",
                rules_version=1,
            ),
        ])
        db.flush()
        db.add_all([
            StudentAccountLink(
                tenant_id=TENANT_ID,
                student_id=STUDENT_PROFILE_ID,
                user_id=STUDENT_ID,
                link_status="ACTIVE",
                bound_login_name="202688013",
                bound_student_no="202688013",
                source="IDENTITY_IMPORT",
            ),
            UserRole(
                tenant_id=TENANT_ID,
                user_id=STAFF_ID,
                role_id=STAFF_ROLE_ID,
                status="ACTIVE",
            ),
            UserRole(
                tenant_id=TENANT_ID,
                user_id=MENTOR_ID,
                role_id=MENTOR_ROLE_ID,
                status="ACTIVE",
            ),
            UserRole(
                tenant_id=TENANT_ID,
                user_id=STUDENT_ID,
                role_id=STUDENT_ROLE_ID,
                status="ACTIVE",
            ),
        ])
        db.commit()
        print({
            "tenantId": TENANT_ID,
            "staff": "yiyang.fullstack.admin",
            "mentor": "yiyang.fullstack.mentor",
            "student": "202688013",
            "batchId": BATCH_ID,
        })
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
