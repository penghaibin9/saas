#!/usr/bin/env python3
"""Seed an ephemeral MySQL database and issue short-lived capacity tokens.

This tool is intended only for GitHub Actions/local test environments. It never creates
production credentials and never prints tokens to stdout. Teacher V3 T9 also seeds one
Student360/employment object plus per-context messages so every newly gated route has a real
server object to read in self-contained CI.

Teacher test userIds are synthetic positive integers. That is intentional: the production
message identity resolver can use them directly, so the capacity run measures the inbox query
instead of paying an artificial User-table lookup/CRC fallback on every request.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.db.session import get_sessionmaker
from app.models import EmpStudent, StudentProfile, UnifiedMessage

TENANT_ID = 1000000000000000001
STUDENT_NO = "PERF-STU-001"
TEACHER_MESSAGE_SOURCE = "capacity-gate-teacher"
TEACHER_USER_ID_BASE = 8_500_000_000


def _teacher_user_id(index: int) -> str:
    return str(TEACHER_USER_ID_BASE + int(index))


def _teacher_context(index: int) -> str:
    return f"perf-teacher-context-{index:04d}"


def seed_runtime_data(token_count: int) -> tuple[int, int, int]:
    db = get_sessionmaker()()
    try:
        student = db.scalar(
            select(StudentProfile).where(
                StudentProfile.tenant_id == TENANT_ID,
                StudentProfile.student_no == STUDENT_NO,
            )
        )
        if student is None:
            student = StudentProfile(
                tenant_id=TENANT_ID,
                student_no=STUDENT_NO,
                real_name="容量测试学生",
                grade="2026",
                current_stage="ON_CAMPUS",
                student_status="NORMAL",
                status="ACTIVE",
            )
            db.add(student)
            db.flush()

        employment = db.scalar(
            select(EmpStudent).where(
                EmpStudent.tenant_id == TENANT_ID,
                EmpStudent.student_id == student.id,
                EmpStudent.is_deleted.is_(False),
            )
        )
        if employment is None:
            # EmpStudent is a domain model, not a CommonMixin status-bearing row. Keep the seed
            # aligned to the real ORM contract: lifecycle truth is record_status/verify_status.
            employment = EmpStudent(
                tenant_id=TENANT_ID,
                student_id=student.id,
                student_no=student.student_no,
                name=student.real_name,
                grade=student.grade,
                destination_type="EMPLOYED",
                company_name="容量测试企业",
                job_title="容量测试岗位",
                verify_status="PENDING_VERIFY",
                material_status="SUBMITTED",
                record_status="ACTIVE",
            )
            db.add(employment)
            db.flush()

        # A rerun against the same local DB must stay deterministic instead of multiplying messages.
        db.execute(delete(UnifiedMessage).where(
            UnifiedMessage.tenant_id == TENANT_ID,
            UnifiedMessage.source_module == TEACHER_MESSAGE_SOURCE,
        ))
        now = datetime.utcnow()
        message_count = 0
        specs = (
            ("SYSTEM", "SYSTEM", "NORMAL", "系统通知"),
            ("BUSINESS", "BUSINESS", "NORMAL", "学生动态"),
            ("EMERGENCY", "EMERGENCY", "EMERGENCY", "风险预警"),
            ("TODO_NOTICE", "TODO", "IMPORTANT", "催办提醒"),
        )
        for index in range(1, token_count + 1):
            receiver_uid = int(_teacher_user_id(index))
            context = _teacher_context(index)
            for offset, (message_type, category, priority, title) in enumerate(specs):
                db.add(UnifiedMessage(
                    tenant_id=TENANT_ID,
                    receiver_id=receiver_uid,
                    receiver_user_id=receiver_uid,
                    receiver_type="STAFF",
                    receiver_context_key=context,
                    source_module=TEACHER_MESSAGE_SOURCE,
                    message_type=message_type,
                    category=category,
                    priority=priority,
                    title=f"{title} {index}",
                    content="Teacher V3 T9 本地容量门禁消息，不含真实人员信息。",
                    status="UNREAD",
                    require_ack=message_type == "EMERGENCY",
                    delivered_at=now - timedelta(seconds=offset),
                    created_at=now - timedelta(seconds=offset),
                ))
                message_count += 1
        db.commit()
        return int(student.id), int(employment.id), message_count
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
            "userId": _teacher_user_id(index),
            "loginName": f"PERF-TEACHER-{index:04d}",
            "realName": "容量测试教师",
            "userType": "TEACHER",
            "tid": "perf-local",
            "tenantId": str(TENANT_ID),
            "activeContextId": _teacher_context(index),
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed local capacity data")
    parser.add_argument("--out", type=Path, default=ROOT / "performance/secrets")
    parser.add_argument("--token-count", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.token_count <= 1000:
        raise SystemExit("token-count must be between 1 and 1000")
    student_id, employment_id, message_count = seed_runtime_data(args.token_count)
    write_tokens(args.out, args.token_count)
    print(
        f"seeded_student=1 student_id={student_id} employment_id={employment_id} "
        f"teacher_messages={message_count} student_tokens={args.token_count} "
        f"teacher_tokens={args.token_count}"
    )


if __name__ == "__main__":
    main()
