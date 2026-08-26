#!/usr/bin/env python3
"""SEED_ONLY prerequisites for GD-012/016/017 targeted Browser First.

This script intentionally creates only prerequisite truth in isolated E2E MySQL.
The target business commands (peer assign/review/rectify, excellent nomination/reviews,
risk scan/accept/process/close) are executed by real browser UI in Playwright.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_sessionmaker
from app.models import FileObject, GraduationBatch, GraduationFinal, GraduationGrade, GraduationMentor, GraduationStudent, StudentProfile

TENANT_ID = 1000000000000000007
RUN_ID = str(os.getenv("GITHUB_RUN_ID") or "local").strip()
BATCH_NO = f"GD-GAP5-{RUN_ID}"
BATCH_NAME = f"E2E GD五项补测 {RUN_ID}"
STUDENTS = {
    "A": ("E2E20260001", "E2E学生A"),
    "B": ("E2E20260002", "E2E学生B"),
    "C": ("E2E20260003", "E2E学生C"),
}


def _ensure_student(db, batch, profile, *, name: str, mentor_id: int | None, stage: str) -> GraduationStudent:
    row = db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == TENANT_ID,
        GraduationStudent.batch_id == batch.id,
        GraduationStudent.student_id == profile.id,
        GraduationStudent.is_deleted.is_(False),
    )).first()
    if row is None:
        row = GraduationStudent(
            tenant_id=TENANT_ID,
            batch_id=batch.id,
            student_id=profile.id,
            student_no=profile.student_no,
            name=name,
            class_id=str(profile.class_id or ""),
            college_id=str(profile.college_id or ""),
            major_id=str(profile.major_id or ""),
            eligibility_status="QUALIFIED",
            mentor_id=mentor_id,
            advisor_name="E2E指导教师A" if mentor_id else None,
            stage=stage,
            record_status="ACTIVE",
        )
        db.add(row)
        db.flush()
    else:
        row.eligibility_status = "QUALIFIED"
        row.stage = stage
        row.record_status = "ACTIVE"
        row.is_deleted = False
        if mentor_id:
            row.mentor_id = mentor_id
            row.advisor_name = "E2E指导教师A"
    return row


def main() -> int:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    if not any(x in str(os.getenv("DATABASE_URL") or "").lower() for x in ("e2e", "test")):
        raise SystemExit("refusing non-E2E database")

    db = get_sessionmaker()()
    try:
        profiles = {}
        for key, (student_no, _) in STUDENTS.items():
            profile = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == TENANT_ID,
                StudentProfile.student_no == student_no,
                StudentProfile.is_deleted.is_(False),
            )).first()
            if not profile:
                raise SystemExit(f"missing canonical E2E student profile: {student_no}")
            profiles[key] = profile

        mentor = db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == TENANT_ID,
            GraduationMentor.teacher_no == "e2e_advisor_a",
            GraduationMentor.is_deleted.is_(False),
        )).first()
        if mentor is None:
            mentor = GraduationMentor(
                tenant_id=TENANT_ID,
                teacher_no="e2e_advisor_a",
                teacher_name="E2E指导教师A",
                mentor_type="INTERNAL",
                title="讲师",
                research_direction="GD五项补测",
                max_capacity=20,
                current_count=0,
                qualification_status="QUALIFIED",
            )
            db.add(mentor)
            db.flush()
        else:
            mentor.qualification_status = "QUALIFIED"
            mentor.is_deleted = False

        batch = db.scalars(select(GraduationBatch).where(
            GraduationBatch.tenant_id == TENANT_ID,
            GraduationBatch.batch_no == BATCH_NO,
        )).first()
        if batch is None:
            batch = GraduationBatch(
                tenant_id=TENANT_ID,
                batch_name=BATCH_NAME,
                batch_no=BATCH_NO,
                academic_year="2025-2026",
                grade_year="2026届",
                planned_count=3,
                status="RUNNING",
                archive_status="NOT_ARCHIVED",
                stage_config=[],
                rules_config={},
            )
            db.add(batch)
            db.flush()
        else:
            batch.status = "RUNNING"
            batch.is_deleted = False

        gd_a = _ensure_student(db, batch, profiles["A"], name=STUDENTS["A"][1], mentor_id=mentor.id, stage="DEFENSE")
        gd_b = _ensure_student(db, batch, profiles["B"], name=STUDENTS["B"][1], mentor_id=None, stage="FINAL_CHECK")
        gd_c = _ensure_student(db, batch, profiles["C"], name=STUDENTS["C"][1], mentor_id=None, stage="TOPIC_SELECTING")

        # GD-012 / GD-016 prerequisite: a frozen, approved formal final with a real readable FileObject.
        payload = (f"GD-012 frozen final evidence {RUN_ID}\n" * 20).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        file_key = f"graduation/gap5/{RUN_ID}/gd012-final.txt"
        target = Path(settings.UPLOAD_DIR or "./uploads") / file_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

        file_row = db.scalars(select(FileObject).where(
            FileObject.tenant_id == TENANT_ID,
            FileObject.file_key == file_key,
            FileObject.is_deleted.is_(False),
        )).first()
        if file_row is None:
            file_row = FileObject(
                tenant_id=TENANT_ID,
                file_key=file_key,
                file_name=f"GD012-冻结定稿-{RUN_ID}.txt",
                ext="txt",
                mime_type="text/plain",
                size_bytes=len(payload),
                sha256=digest,
                biz_type="GRADUATION_MATERIAL",
                biz_id=str(gd_a.id),
                visibility="PRIVATE",
                security_level="NORMAL",
                status="AVAILABLE",
                storage_backend="local",
                storage_zone="ACTIVE",
                object_key=file_key,
                upload_source="SYSTEM",
                scan_required=False,
                scan_status="NOT_REQUIRED",
                available_at=datetime.now(timezone.utc),
            )
            db.add(file_row)
            db.flush()

        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == TENANT_ID,
            GraduationFinal.gd_student_id == gd_a.id,
            GraduationFinal.final_type == "定稿",
            GraduationFinal.version == "v-gap5-1",
            GraduationFinal.is_deleted.is_(False),
        )).first()
        if final is None:
            final = GraduationFinal(
                tenant_id=TENANT_ID,
                gd_student_id=gd_a.id,
                final_type="定稿",
                version="v-gap5-1",
                submit_at=datetime.now(timezone.utc),
                plagiarism_rate="8.0%",
                plagiarism_status="已检测",
                status="APPROVED",
                active_key=None,
                reviewer="E2E补测审核",
                review_comment="正式定稿前置条件已由 SEED_ONLY 建立",
                review_time=datetime.now(timezone.utc),
                attachments_json=[{"fileId": str(file_row.id), "fileName": file_row.file_name}],
            )
            db.add(final)
            db.flush()
        else:
            final.status = "APPROVED"
            final.attachments_json = [{"fileId": str(file_row.id), "fileName": file_row.file_name}]

        grade = db.scalars(select(GraduationGrade).where(
            GraduationGrade.tenant_id == TENANT_ID,
            GraduationGrade.gd_student_id == gd_a.id,
            GraduationGrade.is_deleted.is_(False),
        )).first()
        if grade is None:
            grade = GraduationGrade(
                tenant_id=TENANT_ID,
                gd_student_id=gd_a.id,
                advisor_score=92,
                reviewer_score=91,
                defense_score=93,
                total_score=92,
                grade_level="优秀",
                status="PUBLISHED",
                calculated_at=datetime.now(timezone.utc),
                reviewed_by="E2E补测",
                reviewed_at=datetime.now(timezone.utc),
                published_by="E2E补测",
                published_at=datetime.now(timezone.utc),
            )
            db.add(grade)
        else:
            grade.total_score = 92
            grade.grade_level = "优秀"
            grade.status = "PUBLISHED"
            grade.published_at = datetime.now(timezone.utc)

        db.commit()
        fixture = {
            "runId": RUN_ID,
            "batchId": str(batch.id),
            "batchNo": batch.batch_no,
            "batchName": batch.batch_name,
            "mentorId": str(mentor.id),
            "students": {
                "A": {"gdStudentId": str(gd_a.id), "studentNo": STUDENTS["A"][0], "name": STUDENTS["A"][1]},
                "B": {"gdStudentId": str(gd_b.id), "studentNo": STUDENTS["B"][0], "name": STUDENTS["B"][1]},
                "C": {"gdStudentId": str(gd_c.id), "studentNo": STUDENTS["C"][0], "name": STUDENTS["C"][1]},
            },
            "fileId": str(file_row.id),
            "finalId": str(final.id),
        }
        out = Path("../e2e/runtime-logs/gap-five-fixture.json")
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
