"""Seed only student-affairs prerequisites for the Playwright leave lifecycle.

The script binds the dedicated E2E counselor to the E2E student's administrative
class in the isolated sandbox-school database. It deliberately does not create
CsLeave, workflow tasks, cancel records or audit rows: every business transition
must be produced by visible browser interactions.
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
from app.models import (
    AffairsCounselorAssignment,
    Role,
    SchoolClass,
    StudentProfile,
    Tenant,
    User,
    UserRole,
)

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"
STUDENT_NO = "E2E20260001"
COUNSELOR_LOGIN = "e2e_advisor_a"
COUNSELOR_ROLE = "COUNSELOR"
DEFAULT_FIXTURE_PATH = "../e2e/runtime/student-affairs-fixture.json"


def assert_safe_target() -> None:
    env_name = str(os.getenv("APP_ENV") or "").lower()
    deploy_mode = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env_name in {"prod", "production"} or deploy_mode in {"prod", "production"}:
        raise SystemExit("refusing to seed student-affairs E2E prerequisites in production")
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
        raise SystemExit("student-affairs E2E seed only accepts a local database")


def fixture_path() -> Path:
    return Path(os.getenv("E2E_STUDENT_AFFAIRS_FIXTURE_FILE") or DEFAULT_FIXTURE_PATH).resolve()


def require_tenant(db) -> Tenant:
    tenant = db.get(Tenant, TENANT_ID)
    if tenant is None or tenant.is_deleted:
        raise SystemExit(
            f"tenant {TENANT_CODE}/{TENANT_ID} is missing; run the E2E tenant bootstrap first"
        )
    if tenant.tenant_code != TENANT_CODE:
        raise SystemExit(
            f"tenant id {TENANT_ID} belongs to {tenant.tenant_code!r}, refusing student-affairs E2E seed"
        )
    if tenant.status != "ACTIVE":
        raise SystemExit(
            f"tenant {TENANT_CODE}/{TENANT_ID} is not active, refusing student-affairs E2E seed"
        )
    return tenant


def require_student_and_class(db) -> tuple[StudentProfile, SchoolClass]:
    student = db.scalars(
        select(StudentProfile).where(
            StudentProfile.tenant_id == TENANT_ID,
            StudentProfile.student_no == STUDENT_NO,
            StudentProfile.is_deleted.is_(False),
        )
    ).first()
    if student is None:
        raise SystemExit(
            f"student {TENANT_CODE}/{STUDENT_NO} is missing; run the E2E identity bootstrap first"
        )
    school_class = db.get(SchoolClass, student.class_id) if student.class_id else None
    if school_class is None or school_class.tenant_id != TENANT_ID or school_class.is_deleted:
        raise SystemExit(f"student {STUDENT_NO} has no active administrative class")
    return student, school_class


def require_counselor(db) -> User:
    counselor = db.scalars(
        select(User).where(
            User.tenant_id == TENANT_ID,
            User.login_name == COUNSELOR_LOGIN,
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        )
    ).first()
    if counselor is None:
        raise SystemExit(
            f"counselor {TENANT_CODE}/{COUNSELOR_LOGIN} is missing; run the E2E identity bootstrap first"
        )

    role = db.scalars(
        select(Role).where(
            Role.tenant_id == TENANT_ID,
            Role.role_code == COUNSELOR_ROLE,
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
        )
    ).first()
    if role is None:
        raise SystemExit(f"role {COUNSELOR_ROLE} is missing in {TENANT_CODE}")
    linked = db.scalars(
        select(UserRole).where(
            UserRole.tenant_id == TENANT_ID,
            UserRole.user_id == counselor.id,
            UserRole.role_id == role.id,
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
        )
    ).first()
    if linked is None:
        raise SystemExit(f"{COUNSELOR_LOGIN} does not have active role {COUNSELOR_ROLE}")
    return counselor


def ensure_assignment(
    db,
    student: StudentProfile,
    school_class: SchoolClass,
    counselor: User,
    now: datetime,
) -> AffairsCounselorAssignment:
    # The database is a disposable local E2E database. End any competing active
    # assignment for this one fixture class so the workflow assignee is deterministic.
    active = db.scalars(
        select(AffairsCounselorAssignment).where(
            AffairsCounselorAssignment.tenant_id == TENANT_ID,
            AffairsCounselorAssignment.class_id == school_class.id,
            AffairsCounselorAssignment.status == "ACTIVE",
            AffairsCounselorAssignment.is_deleted.is_(False),
        )
    ).all()
    current = None
    for row in active:
        if int(row.user_id) == int(counselor.id):
            current = row
            continue
        row.status = "ENDED"
        row.effective_to = now
        row.reason = "Replaced only inside isolated Playwright E2E database"
        row.version = int(row.version or 0) + 1

    if current is None:
        current = AffairsCounselorAssignment(
            tenant_id=TENANT_ID,
            class_id=school_class.id,
            user_id=counselor.id,
            duty_type="PRIMARY",
            status="ACTIVE",
            effective_from=now - timedelta(days=1),
            effective_to=None,
            reason="Playwright student-affairs interaction prerequisite",
        )
        db.add(current)
        db.flush()
    else:
        current.duty_type = "PRIMARY"
        current.status = "ACTIVE"
        current.effective_from = now - timedelta(days=1)
        current.effective_to = None
        current.reason = "Playwright student-affairs interaction prerequisite"
        current.is_deleted = False

    school_class.counselor_id = counselor.id
    return current


def main() -> int:
    assert_safe_target()
    now = datetime.utcnow()
    db = get_sessionmaker()()
    try:
        require_tenant(db)
        student, school_class = require_student_and_class(db)
        counselor = require_counselor(db)
        assignment = ensure_assignment(db, student, school_class, counselor, now)
        db.commit()

        payload = {
            "tenantCode": TENANT_CODE,
            "studentId": str(student.id),
            "studentNo": student.student_no,
            "studentName": student.real_name,
            "classId": str(school_class.id),
            "className": school_class.class_name,
            "counselorUserId": str(counselor.id),
            "counselorLogin": counselor.login_name,
            "counselorName": counselor.real_name,
            "assignmentId": str(assignment.id),
        }
        target = fixture_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[e2e-student-affairs-seed] ready:", json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
