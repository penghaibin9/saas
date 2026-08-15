"""Playwright-only U4 process-context scale fixture.

Creates 130 neutral GraduationStudent rows in the isolated E2E MySQL batch so the
real browser can prove student #127 deep-link/F5/save/cancel context preservation.
It does not create guidance records, plans, midterm conclusions, files, scores,
KPI values, or review results. Those interactions must still use production APIs/UI.
"""
from __future__ import annotations

import json
import os
import sys

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import GraduationStudent

COUNT = 130
TARGET_INDEX = 127


def _assert_isolated_e2e_database() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS", "").strip().lower() != "true":
        raise RuntimeError("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    url = (os.getenv("DATABASE_URL") or os.getenv("TEST_DATABASE_URL") or "").lower()
    if "e2e" not in url and "test" not in url:
        raise RuntimeError("DATABASE_URL must contain e2e or test")
    if not any(host in url for host in ("127.0.0.1", "localhost", "@mysql", "mysql:")):
        raise RuntimeError("U4 process fixture only accepts an isolated local/test database")


def main() -> int:
    _assert_isolated_e2e_database()
    if len(sys.argv) != 2:
        raise SystemExit("usage: e2e_seed_graduation_process_context.py <reference_gd_student_id>")

    reference_id = int(sys.argv[1])
    db = get_sessionmaker()()
    try:
        reference = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == reference_id,
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        )).first()
        if reference is None:
            raise RuntimeError(f"graduation student {reference_id} is not active")

        prefix = f"U4CTX{reference.id}-"
        existing = {
            str(row.student_no): row
            for row in db.scalars(select(GraduationStudent).where(
                GraduationStudent.tenant_id == reference.tenant_id,
                GraduationStudent.batch_id == reference.batch_id,
                GraduationStudent.student_no.like(f"{prefix}%"),
                GraduationStudent.is_deleted.is_(False),
            )).all()
        }

        rows = []
        for index in range(1, COUNT + 1):
            student_no = f"{prefix}{index:04d}"
            row = existing.get(student_no)
            if row is None:
                row = GraduationStudent(
                    tenant_id=reference.tenant_id,
                    batch_id=reference.batch_id,
                    student_no=student_no,
                    name=f"U4深链学生{index:04d}",
                    class_name=f"软件U4-{(index - 1) // 50 + 1:02d}班",
                    topic_title=f"U4过程上下文课题{index:04d}",
                    stage="GUIDING",
                    record_status="ACTIVE",
                    mentor_id=reference.mentor_id,
                    advisor_name=reference.advisor_name,
                    college_id=reference.college_id,
                    major_id=getattr(reference, "major_id", None),
                )
                db.add(row)
                db.flush()
            rows.append(row)

        db.commit()
        target = rows[TARGET_INDEX - 1]
        print(json.dumps({
            "count": COUNT,
            "targetIndex": TARGET_INDEX,
            "targetId": str(target.id),
            "studentNo": target.student_no,
            "studentName": target.name,
            "className": target.class_name,
            "batchId": str(reference.batch_id),
        }, ensure_ascii=False))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
