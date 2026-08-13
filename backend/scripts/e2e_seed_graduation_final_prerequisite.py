"""Playwright-only graduation final prerequisite seed.

Only mutates the isolated E2E MySQL student's process prerequisite so the browser can
exercise the real file upload -> mobile final submit -> staff final review read chain.
It does not create a final, file, review result, plagiarism result, KPI, or screenshot data.
Those must still be produced/read through the real HTTP APIs.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import GraduationMidterm, GraduationStudent


def _assert_isolated_e2e_database() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS", "").strip().lower() != "true":
        raise RuntimeError("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    url = (os.getenv("DATABASE_URL") or os.getenv("TEST_DATABASE_URL") or "").lower()
    if "e2e" not in url and "test" not in url:
        raise RuntimeError("DATABASE_URL must contain e2e or test")
    if not any(host in url for host in ("127.0.0.1", "localhost", "@mysql", "mysql:")):
        raise RuntimeError("graduation final prerequisite seed only accepts an isolated local/test database")


def main() -> int:
    _assert_isolated_e2e_database()
    if len(sys.argv) != 2:
        raise SystemExit("usage: e2e_seed_graduation_final_prerequisite.py <gd_student_id>")
    student_id = int(sys.argv[1])
    db = get_sessionmaker()()
    try:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == student_id,
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        if not student:
            raise RuntimeError(f"graduation student {student_id} is not active")
        student.stage = "FINAL_CHECK"
        student.midterm_conclusion = "通过"
        midterm = db.scalars(select(GraduationMidterm).where(
            GraduationMidterm.tenant_id == student.tenant_id,
            GraduationMidterm.gd_student_id == student.id,
            GraduationMidterm.is_deleted.is_(False),
        ).with_for_update()).first()
        if midterm is None:
            midterm = GraduationMidterm(
                tenant_id=student.tenant_id,
                gd_student_id=student.id,
                batch_id=student.batch_id,
                status="CHECKED_PASS",
                conclusion="PASS",
                check_comment="Playwright isolated final-review visual prerequisite",
                checked_at=datetime.now(timezone.utc),
                check_by="Playwright fixture",
            )
            db.add(midterm)
        else:
            midterm.batch_id = student.batch_id
            midterm.status = "CHECKED_PASS"
            midterm.conclusion = "PASS"
            midterm.check_comment = "Playwright isolated final-review visual prerequisite"
            midterm.checked_at = datetime.now(timezone.utc)
            midterm.check_by = "Playwright fixture"
        db.commit()
        print(f"graduation final prerequisite ready: student={student.id} batch={student.batch_id}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
