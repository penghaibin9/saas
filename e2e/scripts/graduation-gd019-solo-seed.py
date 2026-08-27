#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    GraduationBatch,
    GraduationDefenseGroup,
    GraduationGrade,
    GraduationPeerReview,
    GraduationStudent,
    StudentProfile,
)

TENANT_ID = 1000000000000000007
RUN_ID = str(os.getenv("GITHUB_RUN_ID") or "local").strip()
BATCH_NO = f"GD019-SOLO-{RUN_ID}"
BATCH_NAME = f"E2E GD019 SOLO {RUN_ID}"
GROUP_NAME = f"GD019-通知导出-{RUN_ID}"


def canonical_profile(db, student_no: str):
    row = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == TENANT_ID,
        StudentProfile.student_no == student_no,
        StudentProfile.is_deleted.is_(False),
    )).first()
    if row is None:
        raise SystemExit(f"missing canonical {student_no} profile")
    return row


def add_student(db, batch_id: int, profile, name: str):
    row = GraduationStudent(
        tenant_id=TENANT_ID,
        batch_id=batch_id,
        student_id=profile.id,
        student_no=profile.student_no,
        name=name,
        class_id=str(profile.class_id or ""),
        college_id=str(profile.college_id or ""),
        major_id=str(profile.major_id or ""),
        eligibility_status="QUALIFIED",
        stage="DEFENSE",
        record_status="ACTIVE",
    )
    db.add(row)
    db.flush()
    return row


def main() -> int:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    if not any(x in str(os.getenv("DATABASE_URL") or "").lower() for x in ("e2e", "test")):
        raise SystemExit("refusing non-E2E database")

    db = get_sessionmaker()()
    try:
        profile_a = canonical_profile(db, "E2E20260001")
        profile_b = canonical_profile(db, "E2E20260002")

        batch = GraduationBatch(
            tenant_id=TENANT_ID,
            batch_name=BATCH_NAME,
            batch_no=BATCH_NO,
            academic_year="2025-2026",
            grade_year="2026届",
            planned_count=2,
            status="RUNNING",
            archive_status="NOT_ARCHIVED",
            stage_config=[],
            rules_config={},
        )
        db.add(batch)
        db.flush()

        student_a = add_student(db, batch.id, profile_a, "E2E学生A")
        student_b = add_student(db, batch.id, profile_b, "E2E学生B")

        group = GraduationDefenseGroup(
            tenant_id=TENANT_ID,
            batch_id=batch.id,
            group_name=GROUP_NAME,
            defense_date="2026-09-18 09:00",
            location="GD019 SOLO A301",
            chair="E2E指导教师A",
            members_json=[{"mentorId": "0", "name": "E2E独立评委", "teacherNo": "gd019_member"}],
            secretary="E2E评阅教师",
            student_count=1,
            conflict="",
            published=True,
        )
        db.add(group)
        db.flush()
        student_b.defense_group_id = group.id
        student_b.defense_group = group.group_name

        peer = GraduationPeerReview(
            tenant_id=TENANT_ID,
            gd_student_id=student_a.id,
            reviewer_gd_student_id=student_b.id,
            task_version=1,
            opinion="GD019 统计真实前置：互查意见完整。",
            rectify_note="GD019 统计真实前置：已完成整改。",
            status="RECTIFIED",
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(peer)

        grade = GraduationGrade(
            tenant_id=TENANT_ID,
            gd_student_id=student_a.id,
            advisor_score=92,
            reviewer_score=91,
            defense_score=93,
            total_score=92,
            grade_level="优秀",
            status="PUBLISHED",
            calculated_at=datetime.now(timezone.utc),
            reviewed_by="GD019 SOLO",
            reviewed_at=datetime.now(timezone.utc),
            published_by="GD019 SOLO",
            published_at=datetime.now(timezone.utc),
        )
        db.add(grade)
        db.commit()

        fixture = {
            "runId": RUN_ID,
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "groupId": str(group.id),
            "groupName": group.group_name,
            "students": {
                "A": {"gdStudentId": str(student_a.id), "studentNo": student_a.student_no, "name": student_a.name},
                "B": {"gdStudentId": str(student_b.id), "studentNo": student_b.student_no, "name": student_b.name},
            },
            "peerId": str(peer.id),
            "gradeId": str(grade.id),
        }
        out = Path("../e2e/runtime-logs/gd019-solo-fixture.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(fixture, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
