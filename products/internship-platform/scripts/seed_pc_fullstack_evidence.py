#!/usr/bin/env python3
"""Seed the smallest real MySQL fixture for Standalone PC full-stack browser evidence."""
from __future__ import annotations

from datetime import datetime

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
STUDENT_PROFILE_ID = 88131
BATCH_ID = 88141


def main() -> None:
    db = get_sessionmaker()()
    try:
        db.execute(delete(StudentAccountLink).where(StudentAccountLink.tenant_id == TENANT_ID))
        db.execute(delete(StudentProfile).where(StudentProfile.tenant_id == TENANT_ID))
        db.execute(delete(UserRole).where(UserRole.tenant_id == TENANT_ID))
        db.execute(delete(Role).where(Role.tenant_id == TENANT_ID))
        db.execute(delete(InternshipBatch).where(InternshipBatch.tenant_id == TENANT_ID))
        db.execute(delete(User).where(User.tenant_id == TENANT_ID))
        db.execute(delete(Tenant).where(Tenant.id == TENANT_ID))
        db.commit()

        tenant = Tenant(
            id=TENANT_ID,
            tenant_code="FULLSTACK",
            school_name="全栈浏览器验收学校",
            deploy_mode="SAAS",
            db_mode="SHARED",
            status="ACTIVE",
        )
        staff_role = Role(
            id=STAFF_ROLE_ID,
            tenant_id=TENANT_ID,
            role_code="SCHOOL_ADMIN",
            role_name="学校管理员",
            role_type="SYSTEM",
            status="ACTIVE",
        )
        student_role = Role(
            id=STUDENT_ROLE_ID,
            tenant_id=TENANT_ID,
            role_code="STUDENT",
            role_name="学生",
            role_type="SYSTEM",
            status="ACTIVE",
        )
        staff = User(
            id=STAFF_ID,
            tenant_id=TENANT_ID,
            login_name="fullstack.admin",
            real_name="全栈验收管理员",
            password_hash=hash_password("Fullstack-Staff-2026!"),
            user_type="SCHOOL_ADMIN",
            status="ACTIVE",
            must_change_password=False,
            credential_version=0,
        )
        student = User(
            id=STUDENT_ID,
            tenant_id=TENANT_ID,
            login_name="202688112",
            real_name="全栈验收学生",
            password_hash=hash_password("Fullstack-Student-2026!"),
            user_type="STUDENT",
            status="ACTIVE",
            must_change_password=False,
            credential_version=0,
        )
        profile = StudentProfile(
            id=STUDENT_PROFILE_ID,
            tenant_id=TENANT_ID,
            student_no="202688112",
            real_name="全栈验收学生",
            current_stage="ENROLLED",
            student_status="NORMAL",
            status="ACTIVE",
        )
        link = StudentAccountLink(
            tenant_id=TENANT_ID,
            student_id=STUDENT_PROFILE_ID,
            user_id=STUDENT_ID,
            link_status="ACTIVE",
            bound_login_name="202688112",
            bound_student_no="202688112",
            source="IDENTITY_IMPORT",
        )
        batch = InternshipBatch(
            id=BATCH_ID,
            tenant_id=TENANT_ID,
            batch_name="2026岗位实习全栈验收",
            batch_no="FULLSTACK-2026",
            academic_year="2026-2027",
            term="1",
            start_date=datetime(2026, 9, 1),
            end_date=datetime(2027, 1, 31),
            planned_count=1,
            status="RUNNING",
            rules_version=1,
            archive_status="NOT_ARCHIVED",
        )
        db.add_all([
            tenant,
            staff_role,
            student_role,
            staff,
            student,
            profile,
            link,
            batch,
            UserRole(
                tenant_id=TENANT_ID,
                user_id=STAFF_ID,
                role_id=STAFF_ROLE_ID,
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
            "tenantCode": tenant.tenant_code,
            "staffLogin": staff.login_name,
            "studentLogin": student.login_name,
            "batchId": batch.id,
            "batchNo": batch.batch_no,
        })
    finally:
        db.close()


if __name__ == "__main__":
    main()
