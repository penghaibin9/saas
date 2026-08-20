"""Seed B-W4 cross-line formation provenance browser facts after the sealed INT overlay."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

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
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "e2e" / "academic-b-w4-formation-fixture.json"
BOOTSTRAP_COLLEGE = "E2E智能制造学院"
BOOTSTRAP_MAJOR = "E2E工业机器人技术"
BOOTSTRAP_CLASS = "E2E机器人2401班"


def _assert_safe_target() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("academic B W4 formation seed requires an e2e/test database")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("refusing production/staging academic B W4 formation seed")
    if urlparse(db_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("academic B W4 formation seed only accepts a local database")


def _program_course(*, course, program_id: int, mode: str):
    return AaProgramCourse(
        tenant_id=TID,
        program_id=program_id,
        course_id=course.id,
        course_name=course.course_name,
        open_term_no=1,
        module="MAJOR_CORE",
        credit_snapshot=getattr(course, "credit", None) or 2,
        formation_mode=mode,
    )


def _task(*, batch, course, klass, source, mode: str, teacher_key: str, teacher_name: str):
    return AaTeachingTask(
        tenant_id=TID,
        batch_id=batch.id,
        course_id=course.id,
        course_code=course.course_code,
        course_name=course.course_name,
        class_id=klass.id,
        teaching_class_name=klass.class_name,
        teacher_key=teacher_key,
        teacher_name=teacher_name,
        expected_students=36,
        weekly_hours=2,
        total_hours=32,
        start_week=1,
        end_week=16,
        source_program_course_id=source.id,
        formation_mode=mode,
        status="READY",
    )


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
            raise RuntimeError("formation handoff requires the authoritative current published term seed")

        course = db.scalars(select(AaCourse).where(
            AaCourse.tenant_id == TID,
            AaCourse.course_code == "E2E-B-W1-001",
            AaCourse.is_deleted.is_(False),
        )).first()
        if course is None:
            raise RuntimeError("formation handoff requires the authoritative B course seed")

        # Reuse the exact organization names expected by the existing official
        # identity-import bootstrap.  This keeps permission enforcement intact:
        # the bootstrap discovers these rows instead of creating org nodes via API.
        college = College(
            tenant_id=TID,
            college_name=BOOTSTRAP_COLLEGE,
            code="E2E-COL-GD",
            status="ACTIVE",
        )
        db.add(college)
        db.flush()
        major = Major(
            tenant_id=TID,
            college_id=college.id,
            major_name=BOOTSTRAP_MAJOR,
            code="E2E-MAJ-GD",
            status="ACTIVE",
        )
        db.add(major)
        db.flush()
        klass = SchoolClass(
            tenant_id=TID,
            major_id=major.id,
            class_name=BOOTSTRAP_CLASS,
            class_code="E2E-CLS-GD",
            grade="2024",
            status="ACTIVE",
        )
        db.add(klass)
        db.flush()

        task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            college_id=college.id,
            batch_name="B线W4 Formation Handoff READY批次",
            status="APPROVED",
        )
        db.add(task_batch)
        db.flush()

        selectable_source = _program_course(course=course, program_id=99000401, mode="SELECTABLE")
        blocked_source = _program_course(course=course, program_id=99000402, mode="ADMIN_FIXED")
        db.add_all([selectable_source, blocked_source])
        db.flush()

        selectable_task = _task(
            batch=task_batch,
            course=course,
            klass=klass,
            source=selectable_source,
            mode="SELECTABLE",
            teacher_key="E2E-W4-F-SELECTABLE",
            teacher_name="B线W4可选编班教师",
        )
        blocked_task = _task(
            batch=task_batch,
            course=course,
            klass=klass,
            source=blocked_source,
            mode="ADMIN_FIXED",
            teacher_key="E2E-W4-F-BLOCKED",
            teacher_name="B线W4固定编班教师",
        )
        db.add_all([selectable_task, blocked_task])
        db.flush()
        db.commit()

        fixture = {
            "termId": str(term.id),
            "courseId": str(course.id),
            "courseCode": str(course.course_code),
            "courseName": str(course.course_name),
            "className": str(klass.class_name),
            "selectableTaskId": str(selectable_task.id),
            "selectableTeacherName": selectable_task.teacher_name,
            "blockedTaskId": str(blocked_task.id),
            "blockedTeacherName": blocked_task.teacher_name,
            "blockedMessage": "当前教学任务的正式编班模式不允许进入学生选课供给",
        }
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[academic-b-w4-formation-e2e-seed] ready", fixture)
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
