"""Seed only the academic B W1 browser prerequisites in the isolated E2E database.

The browser test creates the selection batch and course offerings through production APIs.
This script only provides stable, authoritative base facts that do not have a public fixture API:
a published/current term and two enabled course-catalog rows.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select, update

from app.db.session import get_sessionmaker
from app.models import AaCourse, AaTerm

TID = 1000000000000000007
YEAR_CODE = "2098-2099"
COURSES = (
    ("E2E-B-W1-001", "B线W1跨端选课甲"),
    ("E2E-B-W1-002", "B线W1跨端选课乙"),
)


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

        ready = []
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
            ready.append(course)
        db.flush()
        db.commit()
        print(
            "[academic-b-e2e-seed] ready",
            {"termId": str(term.id), "courseIds": [str(row.id) for row in ready]},
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
