"""Seed only AA-011 prerequisites that the Selection UI does not own.

The real browser still creates the Selection batch and course offerings.  This script only:
- publishes one authoritative schedule containing two READY teaching tasks at the same slot,
  so Student PC can prove the production time-conflict rule;
- creates one foreign-tenant SelectionCourse id for the explicit tenant-injection negative gate.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    AaScheduleBatch,
    AaScheduleItem,
    AaScheduleScopeHead,
    AaSelectionBatch,
    AaSelectionCourse,
    AaTeachingTask,
    AaTerm,
)

SANDBOX_TID = 1000000000000000007
FOREIGN_TID = 1000000000000000003
ROOT = Path(__file__).resolve().parents[2]
W5_FIXTURE = ROOT / "e2e" / "academic-b-w5-fixture.json"
OUT = ROOT / "e2e" / "academic-aa011-prereq.json"


def _assert_safe_target() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("AA-011 seed requires an e2e/test database")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("refusing production/staging AA-011 seed")
    if urlparse(db_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("AA-011 seed only accepts a local database")


def main() -> int:
    _assert_safe_target()
    fixture = json.loads(W5_FIXTURE.read_text(encoding="utf-8"))
    by_role = {str(row["role"]): row for row in fixture["courses"]}
    race = by_role["PC"]
    conflict = by_role["MINIAPP"]

    db = get_sessionmaker()()
    try:
        term = db.get(AaTerm, int(fixture["termId"]))
        if not term or term.tenant_id != SANDBOX_TID or term.is_deleted:
            raise RuntimeError("AA-011 requires the current sandbox term")
        race_task = db.get(AaTeachingTask, int(race["taskId"]))
        conflict_task = db.get(AaTeachingTask, int(conflict["taskId"]))
        if not race_task or not conflict_task:
            raise RuntimeError("AA-011 READY teaching tasks are missing")

        schedule = AaScheduleBatch(
            tenant_id=SANDBOX_TID,
            term_id=term.id,
            batch_name="AA-011 authoritative conflict schedule",
            status="PUBLISHED",
            publish_at=datetime.utcnow(),
        )
        db.add(schedule)
        db.flush()
        for task in (race_task, conflict_task):
            db.add(AaScheduleItem(
                tenant_id=SANDBOX_TID,
                batch_id=schedule.id,
                task_id=task.id,
                course_id=task.course_id,
                course_name=task.course_name,
                class_id=task.class_id,
                teacher_key=task.teacher_key,
                teacher_name=task.teacher_name,
                weekday=2,
                slot_no=3,
                start_week=1,
                end_week=16,
                week_parity="ALL",
                classroom_text="AA-011冲突课位",
                status="EFFECTIVE",
                source="MANUAL",
            ))
        head = db.scalars(select(AaScheduleScopeHead).where(
            AaScheduleScopeHead.tenant_id == SANDBOX_TID,
            AaScheduleScopeHead.term_id == term.id,
            AaScheduleScopeHead.scope_type == "SCHOOL",
            AaScheduleScopeHead.scope_id == 0,
            AaScheduleScopeHead.is_deleted.is_(False),
        )).first()
        if head is None:
            head = AaScheduleScopeHead(
                tenant_id=SANDBOX_TID,
                term_id=term.id,
                scope_type="SCHOOL",
                scope_id=0,
                active_batch_id=schedule.id,
                version=1,
                published_at=datetime.utcnow(),
            )
            db.add(head)
        else:
            head.active_batch_id = schedule.id
            head.version = int(head.version or 0) + 1
            head.published_at = datetime.utcnow()

        foreign_batch = AaSelectionBatch(
            tenant_id=FOREIGN_TID,
            term_id=None,
            batch_name="AA-011 foreign tenant injection fixture",
            status="OPEN",
        )
        db.add(foreign_batch)
        db.flush()
        foreign_course = AaSelectionCourse(
            tenant_id=FOREIGN_TID,
            batch_id=foreign_batch.id,
            course_id=int(race["courseId"]),
            course_name="AA-011 foreign tenant course",
            teaching_task_id=None,
            credit=2,
            capacity=5,
            min_capacity=0,
            selected_count=0,
            status="OPEN",
        )
        db.add(foreign_course)
        db.commit()
        db.refresh(foreign_course)

        payload = {
            "tenantId": str(SANDBOX_TID),
            "termId": str(term.id),
            "scheduleBatchId": str(schedule.id),
            "race": race,
            "conflict": conflict,
            "foreignTenantId": str(FOREIGN_TID),
            "foreignSelectionCourseId": str(foreign_course.id),
        }
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[AA-011 seed] ready", payload)
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
