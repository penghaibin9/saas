"""Seed only Academic B W3 Task-first browser facts in an isolated E2E database."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    AaClassroom,
    AaCourse,
    AaScheduleBatch,
    AaTeachingTask,
    AaTeachingTaskBatch,
    AaTerm,
    AaTimeSlot,
    College,
    Major,
    SchoolClass,
)

TID = 1000000000000000007
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "e2e" / "academic-b-w3-fixture.json"


def _assert_safe_target() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("academic B W3 seed requires an e2e/test database")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("refusing production/staging academic B W3 seed")
    if urlparse(db_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("academic B W3 seed only accepts a local database")


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
            raise RuntimeError("W3 requires the W1 authoritative current published term seed")
        course = db.scalars(select(AaCourse).where(
            AaCourse.tenant_id == TID,
            AaCourse.course_code == "E2E-B-W1-001",
            AaCourse.is_deleted.is_(False),
        )).first()
        if course is None:
            raise RuntimeError("W3 requires the W1 authoritative course seed")

        college = College(tenant_id=TID, college_name="B线W3软件学院", code="E2EBW3", status="ACTIVE")
        db.add(college); db.flush()
        major = Major(tenant_id=TID, college_id=college.id, major_name="B线W3软件技术", code="E2EBW301", status="ACTIVE")
        db.add(major); db.flush()
        klass = SchoolClass(
            tenant_id=TID, major_id=major.id, class_name="B线W3软件2401",
            class_code="E2E-B-W3-2401", grade="2024", status="ACTIVE",
        )
        db.add(klass); db.flush()

        for slot_no, start, end in ((1, "08:20", "09:05"), (2, "09:15", "10:00")):
            db.add(AaTimeSlot(
                tenant_id=TID, slot_no=slot_no, slot_name=f"第{slot_no}节",
                start_time=start, end_time=end, campus_code="MAIN",
                enabled=True, status="ENABLED",
            ))
        room = AaClassroom(
            tenant_id=TID, building_code="W3A", building_name="W3教学楼",
            room_code="101", room_name="W3教学楼101", capacity=60,
            room_type="LECTURE", campus_code="MAIN", status="AVAILABLE",
        )
        db.add(room); db.flush()

        task_batch = AaTeachingTaskBatch(
            tenant_id=TID, term_id=term.id, college_id=college.id,
            batch_name="B线W3 READY教学任务批次", status="APPROVED",
        )
        db.add(task_batch); db.flush()
        task = AaTeachingTask(
            tenant_id=TID, batch_id=task_batch.id, course_id=course.id,
            course_code=course.course_code, course_name="B线W3 Task-first课程",
            class_id=klass.id, teaching_class_name=klass.class_name,
            teacher_key="E2E-W3-T001", teacher_name="B线W3任课教师",
            expected_students=30, weekly_hours=2, total_hours=28,
            start_week=3, end_week=16, status="READY",
        )
        db.add(task); db.flush()
        schedule = AaScheduleBatch(
            tenant_id=TID, term_id=term.id, college_id=college.id,
            batch_name="B线W3 Task-first课表", status="DRAFT",
        )
        db.add(schedule); db.flush()
        db.commit()

        fixture = {
            "batchId": str(schedule.id),
            "termId": str(term.id),
            "classId": str(klass.id),
            "className": klass.class_name,
            "taskId": str(task.id),
            "taskBatchId": str(task_batch.id),
            "courseName": task.course_name,
            "courseCode": task.course_code,
            "teacherName": task.teacher_name,
            "teacherKey": task.teacher_key,
            "startWeek": 3,
            "endWeek": 16,
            "roomCode": room.room_code,
        }
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[academic-b-w3-e2e-seed] ready", fixture)
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
