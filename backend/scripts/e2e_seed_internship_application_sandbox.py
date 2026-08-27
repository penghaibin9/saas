"""Seed only the prerequisites for the real-browser internship application journey.

This script is intentionally limited to initial master data: it creates/normalizes a
second sandbox student internship record in PREPARING state with no destination.  It
must never create an InternshipApplication, upload a file, review an application or
land a destination; those transitions belong to visible Playwright browser actions.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import InternshipBatch, InternshipRecord, StudentProfile, Tenant, User

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"
STUDENT_NO = "E2E20260002"
MENTOR_LOGIN = "e2e_advisor_a"
DEFAULT_FIXTURE_PATH = "../e2e/runtime/internship-application-fixture.json"


def assert_safe_target() -> None:
    env_name = str(os.getenv("APP_ENV") or "").lower()
    deploy_mode = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env_name in {"prod", "production"} or deploy_mode in {"prod", "production"}:
        raise SystemExit("refusing to seed internship application E2E prerequisites in production")
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("DATABASE_URL looks like a production or staging database")
    parsed = urlparse(db_url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("internship application E2E seed only accepts a local database")


def fixture_path() -> Path:
    return Path(os.getenv("E2E_INTERNSHIP_APPLICATION_FIXTURE_FILE") or DEFAULT_FIXTURE_PATH).resolve()


def main() -> int:
    assert_safe_target()
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TENANT_ID)
        if not tenant or tenant.is_deleted or tenant.tenant_code != TENANT_CODE or tenant.status != "ACTIVE":
            raise SystemExit("sandbox-school tenant is missing or inactive")

        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == TENANT_ID,
            StudentProfile.student_no == STUDENT_NO,
            StudentProfile.is_deleted.is_(False),
        )).first()
        if not student:
            raise SystemExit(f"student {STUDENT_NO} is missing; run interaction account bootstrap first")

        mentor = db.scalars(select(User).where(
            User.tenant_id == TENANT_ID,
            User.login_name == MENTOR_LOGIN,
            User.is_deleted.is_(False),
        )).first()
        if not mentor:
            raise SystemExit(f"mentor {MENTOR_LOGIN} is missing")

        batch = db.scalars(select(InternshipBatch).where(
            InternshipBatch.tenant_id == TENANT_ID,
            InternshipBatch.status == "RUNNING",
            InternshipBatch.is_deleted.is_(False),
        ).order_by(InternshipBatch.id.desc())).first()
        if not batch:
            raise SystemExit("running internship batch is missing; run e2e_seed_internship_sandbox.py first")

        record = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == TENANT_ID,
            InternshipRecord.student_id == student.id,
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
        )).first()
        initial = {
            "advisor_name": mentor.real_name,
            "advisor_user_id": mentor.id,
            "eligibility_status": "QUALIFIED",
            "destination_type": "NONE",
            "enterprise_id": None,
            "enterprise_name": None,
            "position_id": None,
            "position_name": None,
            "enterprise_mentor_name": None,
            "status": "PREPARING",
            "risk_level": "NONE",
            "intern_start_date": datetime.utcnow() + timedelta(days=7),
            "intern_end_date": datetime.utcnow() + timedelta(days=97),
            "remark": "E2E application prerequisite only; application and landing must be browser-created",
        }
        if record is None:
            record = InternshipRecord(
                tenant_id=TENANT_ID,
                student_id=student.id,
                batch_id=batch.id,
                **initial,
            )
            db.add(record)
            db.flush()
        else:
            for key, value in initial.items():
                setattr(record, key, value)
            record.is_deleted = False
        db.commit()

        payload = {
            "tenantCode": TENANT_CODE,
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "internshipId": str(record.id),
            "studentId": str(student.id),
            "studentNo": student.student_no,
            "studentName": student.real_name,
            "mentorUserId": str(mentor.id),
            "mentorLogin": mentor.login_name,
            "mentorName": mentor.real_name,
            "initialStatus": record.status,
            "initialDestinationType": record.destination_type,
        }
        target = fixture_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[e2e-internship-application-seed] ready:", json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
