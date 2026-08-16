"""Seed Academic B W5 student-projection browser facts in an isolated E2E database."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm, StudentProfile

TID = 1000000000000000007
MAIN_STUDENT_NO = "E2E20260001"
FILLER_STUDENT_NO = "E2E20260002"
COURSE_SPECS = (
    ("E2E-B-W1-001", "B线W1跨端选课甲", "B线W5任课教师甲"),
    ("E2E-B-W1-002", "B线W1跨端选课乙", "B线W5任课教师乙"),
    ("E2E-B-W5-003", "B线W5服务器满额阻断", "B线W5任课教师满额"),
)
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "e2e" / "academic-b-w5-fixture.json"


def _assert_safe_target() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("academic B W5 seed requires an e2e/test database")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("refusing production/staging academic B W5 seed")
    if urlparse(db_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("academic B W5 seed only accepts a local database")


def _course(db, code: str, name: str):
    row = db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == TID,
        AaCourse.course_code == code,
        AaCourse.version == 1,
        AaCourse.is_deleted.is_(False),
    )).first()
    if row is None:
        row = AaCourse(
            tenant_id=TID,
            course_code=code,
            course_name=name,
            category="PUBLIC_BASIC",
            nature="ELECTIVE",
            credit=2,
            hours_total=32,
            hours_theory=32,
            hours_practice=0,
            hours_experiment=0,
            hours_computer=0,
            exam_mode="CHECK",
            is_core=False,
            version=1,
            status="ENABLED",
        )
        db.add(row)
        db.flush()
    else:
        row.course_name = name
        row.credit = 2
        row.status = "ENABLED"
        row.is_deleted = False
    return row


def main() -> int:
    _assert_safe_target()
    db = get_sessionmaker()()
    try:
        term = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == TID,
            AaTerm.is_current.is_(True),
            AaTerm.status == "PUBLISHED",
            AaTerm.is_deleted.is_(False),
        )).first()
        if term is None:
            raise RuntimeError("W5 requires the W1 current published term seed")

        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == TID,
            StudentProfile.student_no.in_([MAIN_STUDENT_NO, FILLER_STUDENT_NO]),
            StudentProfile.is_deleted.is_(False),
        )).all()
        by_no = {str(row.student_no): row for row in students}
        main_student = by_no.get(MAIN_STUDENT_NO)
        filler_student = by_no.get(FILLER_STUDENT_NO)
        if main_student is None or filler_student is None:
            raise RuntimeError("W5 requires both official E2E student identities")
        if not main_student.college_id or not main_student.class_id:
            raise RuntimeError("W5 main student must have official college/class identity")

        courses = [_course(db, code, name) for code, name, _teacher in COURSE_SPECS]
        task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            college_id=main_student.college_id,
            batch_name="B线W5学生投影READY教学任务批次",
            status="APPROVED",
        )
        db.add(task_batch)
        db.flush()

        task_rows = []
        for index, (course, spec) in enumerate(zip(courses, COURSE_SPECS), start=1):
            _code, _name, teacher_name = spec
            task = AaTeachingTask(
                tenant_id=TID,
                batch_id=task_batch.id,
                course_id=course.id,
                course_code=course.course_code,
                course_name=course.course_name,
                class_id=main_student.class_id,
                teaching_class_name=f"B线W5教学班{index}",
                teacher_key=f"E2E-W5-T{index:03d}",
                teacher_name=teacher_name,
                expected_students=30,
                weekly_hours=2,
                total_hours=32,
                start_week=1,
                end_week=16,
                status="READY",
            )
            db.add(task)
            db.flush()
            task_rows.append(task)

        db.commit()
        fixture = {
            "termId": str(term.id),
            "mainStudentNo": MAIN_STUDENT_NO,
            "fillerStudentNo": FILLER_STUDENT_NO,
            "taskBatchId": str(task_batch.id),
            "courses": [
                {
                    "courseId": str(course.id),
                    "courseCode": str(course.course_code),
                    "courseName": str(course.course_name),
                    "taskId": str(task.id),
                    "teacherName": str(task.teacher_name),
                    "role": "BLOCKER" if index == 2 else ("PC" if index == 0 else "MINIAPP"),
                }
                for index, (course, task) in enumerate(zip(courses, task_rows))
            ],
        }
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[academic-b-w5-e2e-seed] ready", fixture)
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
