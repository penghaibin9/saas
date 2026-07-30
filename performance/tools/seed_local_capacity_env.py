#!/usr/bin/env python3
"""Seed an ephemeral MySQL database and issue short-lived capacity smoke tokens.

This tool is intended only for GitHub Actions/local test environments. It never creates
production credentials and never prints tokens to stdout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.session import get_sessionmaker
from app.models import StudentProfile

TENANT_ID = 1000000000000000001
STUDENT_NO = "PERF-STU-001"


def seed_student() -> None:
    db = get_sessionmaker()()
    try:
        existing = db.scalar(
            select(StudentProfile).where(
                StudentProfile.tenant_id == TENANT_ID,
                StudentProfile.student_no == STUDENT_NO,
            )
        )
        if existing is None:
            db.add(
                StudentProfile(
                    tenant_id=TENANT_ID,
                    student_no=STUDENT_NO,
                    real_name="容量测试学生",
                    grade="2026",
                    current_stage="ON_CAMPUS",
                    student_status="NORMAL",
                    status="ACTIVE",
                )
            )
            db.commit()
    finally:
        db.close()


def write_tokens(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    student = create_access_token(
        {
            "userId": "perf-student",
            "loginName": STUDENT_NO,
            "realName": "容量测试学生",
            "userType": "STUDENT",
            "tid": "perf-local",
            "tenantId": str(TENANT_ID),
            "activeContextId": "perf-student-context",
            "currentRoleCode": "STUDENT",
            "clientType": "MP",
            "studentNo": STUDENT_NO,
        },
        expires_in=3600,
    )
    teacher = create_access_token(
        {
            "userId": "perf-teacher",
            "loginName": "PERF-TEACHER-001",
            "realName": "容量测试教师",
            "userType": "TEACHER",
            "tid": "perf-local",
            "tenantId": str(TENANT_ID),
            "activeContextId": "perf-teacher-context",
            "currentRoleCode": "SCHOOL_ADMIN",
            "clientType": "MP",
        },
        expires_in=3600,
    )
    (out_dir / "student-tokens.json").write_text(
        json.dumps([student], ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "teacher-tokens.json").write_text(
        json.dumps([teacher], ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    print("seeded_student=1 student_tokens=1 teacher_tokens=1")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed local capacity smoke data")
    parser.add_argument("--out", type=Path, default=Path("performance/secrets"))
    args = parser.parse_args()
    seed_student()
    write_tokens(args.out)


if __name__ == "__main__":
    main()
