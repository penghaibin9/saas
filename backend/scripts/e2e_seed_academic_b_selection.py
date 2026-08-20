"""Seed the Academic B W1 browser prerequisites in the isolated E2E database.

The browser test creates Selection batches and course offerings through production APIs.
This seed provides stable authoritative base facts that do not have a public fixture API:
a published/current term, enabled course-catalog rows, and PROVEN SELECTABLE READY
TeachingTasks whose ProgramCourse provenance satisfies the production Selection contract.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select, update

from app.db.session import get_sessionmaker
from app.models import (
    AaCourse,
    AaProgramCourse,
    AaTeachingTask,
    AaTeachingTaskBatch,
    AaTerm,
    College,
    Major,
    SchoolClass,
)

TID = 1000000000000000007
YEAR_CODE = "2098-2099"
COURSES = (
    ("E2E-B-W1-001", "B线W1跨端选课甲"),
    ("E2E-B-W1-002", "B线W1跨端选课乙"),
)
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "e2e" / "academic-b-w1-fixture.json"


def _assert_safe_target() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("academic B E2E seed requires an e2e/test database")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("refusing production/staging academic B seed")
    host = urlparse(db_url).hostname
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("academic B E2E seed only accepts a local database")


def main() -> int:
    _assert_safe_target()
    db = get_sessionmaker()()
    try:
        db.execute(
            update(AaTerm)
            .where(AaTerm.tenant_id == TID, AaTerm.is_deleted.is_(False))
            .values(is_current=False)
        )
        term = db.scalars(
            select(AaTerm).where(
                AaTerm.tenant_id == TID,
                AaTerm.year_code == YEAR_CODE,
                AaTerm.term_no == 1,
                AaTerm.is_deleted.is_(False),
            )
        ).first()
        now = datetime.utcnow()
        if term is None:
            term = AaTerm(
                tenant_id=TID,
                year_code=YEAR_CODE,
                term_no=1,
                term_name="B线W1浏览器验收学期",
                start_date=now - timedelta(days=7),
                end_date=now + timedelta(days=140),
                teaching_weeks=20,
                exam_week_start=21,
                is_current=True,
                status="PUBLISHED",
            )
            db.add(term)
        else:
            term.term_name = "B线W1浏览器验收学期"
            term.start_date = now - timedelta(days=7)
            term.end_date = now + timedelta(days=140)
            term.teaching_weeks = 20
            term.exam_week_start = 21
            term.is_current = True
            term.status = "PUBLISHED"
            term.is_deleted = False

        courses = []
        for code, name in COURSES:
            course = db.scalars(
                select(AaCourse).where(
                    AaCourse.tenant_id == TID,
                    AaCourse.course_code == code,
                    AaCourse.version == 1,
                    AaCourse.is_deleted.is_(False),
                )
            ).first()
            if course is None:
                course = AaCourse(
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
                db.add(course)
            else:
                course.course_name = name
                course.credit = 2
                course.status = "ENABLED"
                course.is_deleted = False
            courses.append(course)
        db.flush()

        college = College(
            tenant_id=TID,
            college_name="B线W1选课学院",
            code="E2EBW1",
            status="ACTIVE",
        )
        db.add(college)
        db.flush()
        major = Major(
            tenant_id=TID,
            college_id=college.id,
            major_name="B线W1选课专业",
            code="E2EBW101",
            status="ACTIVE",
        )
        db.add(major)
        db.flush()
        klass = SchoolClass(
            tenant_id=TID,
            major_id=major.id,
            class_name="B线W1选课2401",
            class_code="E2E-B-W1-2401",
            grade="2024",
            status="ACTIVE",
        )
        db.add(klass)
        db.flush()

        task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            college_id=college.id,
            batch_name="B线W1 SELECTABLE READY教学任务批次",
            status="APPROVED",
        )
        db.add(task_batch)
        db.flush()

        task_rows = []
        for index, course in enumerate(courses, start=1):
            source = AaProgramCourse(
                tenant_id=TID,
                program_id=99000100 + index,
                course_id=course.id,
                course_name=course.course_name,
                open_term_no=1,
                module="MAJOR_CORE",
                credit_snapshot=getattr(course, "credit", None) or 2,
                formation_mode="SELECTABLE",
            )
            db.add(source)
            db.flush()
            task = AaTeachingTask(
                tenant_id=TID,
                batch_id=task_batch.id,
                course_id=course.id,
                course_code=course.course_code,
                course_name=course.course_name,
                class_id=klass.id,
                teaching_class_name=f"B线W1教学班{index}",
                teacher_key=f"E2E-W1-T{index:03d}",
                teacher_name=f"B线W1任课教师{index}",
                expected_students=30,
                weekly_hours=2,
                total_hours=32,
                start_week=1,
                end_week=16,
                source_program_course_id=source.id,
                formation_mode="SELECTABLE",
                status="READY",
            )
            db.add(task)
            db.flush()
            task_rows.append(task)

        db.commit()
        fixture = {
            "termId": str(term.id),
            "taskBatchId": str(task_batch.id),
            "courses": [
                {
                    "courseId": str(course.id),
                    "courseCode": str(course.course_code),
                    "courseName": str(course.course_name),
                    "taskId": str(task.id),
                }
                for course, task in zip(courses, task_rows)
            ],
        }
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[academic-b-e2e-seed] ready", fixture)
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
