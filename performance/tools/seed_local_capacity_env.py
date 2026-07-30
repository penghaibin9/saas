#!/usr/bin/env python3
"""Seed an ephemeral MySQL database and issue short-lived capacity tokens.

This tool is intended only for GitHub Actions/local test environments. It never creates
production credentials and never prints tokens to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

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


def _student_token(index: int) -> str:
    return create_access_token(
        {
            "userId": f"perf-student-{index:04d}",
            "loginName": STUDENT_NO,
            "realName": "容量测试学生",
            "userType": "STUDENT",
            "tid": "perf-local",
            "tenantId": str(TENANT_ID),
            "activeContextId": f"perf-student-context-{index:04d}",
            "currentRoleCode": "STUDENT",
            "clientType": "MP",
            "studentNo": STUDENT_NO,
        },
        expires_in=3600,
    )


def _teacher_token(index: int) -> str:
    return create_access_token(
        {
            "userId": f"perf-teacher-{index:04d}",
            "loginName": f"PERF-TEACHER-{index:04d}",
            "realName": "容量测试教师",
            "userType": "TEACHER",
            "tid": "perf-local",
            "tenantId": str(TENANT_ID),
            "activeContextId": f"perf-teacher-context-{index:04d}",
            "currentRoleCode": "SCHOOL_ADMIN",
            "clientType": "MP",
        },
        expires_in=3600,
    )


def write_tokens(out_dir: Path, token_count: int) -> None:
    if not 1 <= token_count <= 1000:
        raise SystemExit("token-count must be between 1 and 1000")
    out_dir.mkdir(parents=True, exist_ok=True)
    students = [_student_token(index) for index in range(1, token_count + 1)]
    teachers = [_teacher_token(index) for index in range(1, token_count + 1)]
    (out_dir / "student-tokens.json").write_text(
        json.dumps(students, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "teacher-tokens.json").write_text(
        json.dumps(teachers, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    print(
        f"seeded_student=1 student_tokens={token_count} "
        f"teacher_tokens={token_count}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed local capacity data")
    parser.add_argument("--out", type=Path, default=ROOT / "performance/secrets")
    parser.add_argument("--token-count", type=int, default=1)
    args = parser.parse_args()
    seed_student()
    write_tokens(args.out, args.token_count)


if __name__ == "__main__":
    main()
