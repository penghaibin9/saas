"""Seed the isolated real-browser fixture for W1 post-archive correction.

This script is intentionally direct-DB setup only.  The acceptance actions themselves
(create, same-person denial, second-person approve, reject, Manifest verification) are
performed through the production HTTP/UI paths by Playwright.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import (
    AaArchiveBatch,
    AaTerm,
    AcademicGrade,
    AcademicStudent,
    ArchiveManifest,
    Role,
    Tenant,
    User,
    UserRole,
)
from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as manifest_service

TID = 1000000000000000911
TENANT_CODE = "academic-w1-school"
CREATOR_LOGIN = "academic_w1_admin"
REVIEWER_LOGIN = "academic_w1_reviewer"
PASSWORD = "123456"
YEAR_CODE = "2095-2096"
TERM_NO = 2
TERM_CODE = f"{YEAR_CODE}-{TERM_NO}"
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "e2e" / "academic-archive-correction-w1-fixture.json"


def assert_safe_target() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    if str(os.getenv("APP_ENV") or "").lower() in {"prod", "production"}:
        raise SystemExit("refusing to seed W1 browser fixture in production")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("DATABASE_URL looks like production/staging")
    if urlparse(db_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("W1 browser seed only accepts a local database")


def _ensure_reviewer(db, role: Role) -> User:
    reviewer = db.scalars(select(User).where(
        User.tenant_id == TID,
        User.login_name == REVIEWER_LOGIN,
    )).first()
    if reviewer is None:
        reviewer = User(
            tenant_id=TID,
            login_name=REVIEWER_LOGIN,
            real_name="W1归档纠错二审员",
            password_hash=hash_password(PASSWORD),
            user_type="ADMIN",
            status="ACTIVE",
            must_change_password=False,
        )
        db.add(reviewer)
    else:
        reviewer.real_name = "W1归档纠错二审员"
        reviewer.password_hash = hash_password(PASSWORD)
        reviewer.user_type = "ADMIN"
        reviewer.status = "ACTIVE"
        reviewer.must_change_password = False
        reviewer.is_deleted = False
    db.flush()
    link = db.scalars(select(UserRole).where(
        UserRole.tenant_id == TID,
        UserRole.user_id == reviewer.id,
        UserRole.role_id == role.id,
        UserRole.is_deleted.is_(False),
    )).first()
    if link is None:
        db.add(UserRole(
            tenant_id=TID,
            user_id=reviewer.id,
            role_id=role.id,
            status="ACTIVE",
        ))
    return reviewer


def _grade(db, suffix: int, score: int) -> AcademicGrade:
    student = AcademicStudent(
        tenant_id=TID,
        student_no=f"W1ARCHIVE{suffix:03d}",
        name=f"W1归档纠错学生{suffix}",
        obtained_credits=0,
    )
    db.add(student)
    db.flush()
    row = AcademicGrade(
        tenant_id=TID,
        acad_student_id=student.id,
        course_name=f"W1归档课程{suffix}",
        term=TERM_CODE,
        nature="REQUIRED",
        credit_value=3,
        score=score,
        pass_status="PASSED" if score >= 60 else "FAILED",
        exam_type="FINAL",
        record_status="ACTIVE",
        source="PUBLISH",
        course_code=f"W1A{suffix:03d}",
        course_version=1,
        attempt_no=1,
        effective_policy_code="DEFAULT",
        effective_policy_version=1,
        effective_attempt_strategy="LATEST_ATTEMPT",
        pass_line_snapshot=60,
    )
    db.add(row)
    db.flush()
    return row


def main() -> int:
    assert_safe_target()
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TID)
        if tenant is None or tenant.tenant_code != TENANT_CODE:
            raise SystemExit("run e2e_seed_playwright_tenants.py before W1 fixture seed")
        creator = db.scalars(select(User).where(
            User.tenant_id == TID,
            User.login_name == CREATOR_LOGIN,
            User.is_deleted.is_(False),
        )).first()
        role = db.scalars(select(Role).where(
            Role.tenant_id == TID,
            Role.role_code == "SCHOOL_ADMIN",
            Role.is_deleted.is_(False),
        )).first()
        if creator is None or role is None:
            raise SystemExit("academic W1 creator/role foundation is missing")
        reviewer = _ensure_reviewer(db, role)

        now = datetime.utcnow()
        term = AaTerm(
            tenant_id=TID,
            year_code=YEAR_CODE,
            term_no=TERM_NO,
            term_name="W1归档后纠错浏览器验收学期",
            start_date=now - timedelta(days=180),
            end_date=now - timedelta(days=30),
            teaching_weeks=20,
            exam_week_start=19,
            is_current=False,
            status="PUBLISHED",
        )
        db.add(term)
        db.flush()

        grades = [
            _grade(db, 1, 58),
            _grade(db, 2, 71),
            _grade(db, 3, 64),
            _grade(db, 4, 83),
        ]
        batch = AaArchiveBatch(
            tenant_id=TID,
            batch_name="W1归档后纠错浏览器验收",
            term_id=term.id,
            term_code=TERM_CODE,
            status="ARCHIVED",
            archived_at=now,
            created_by=creator.id,
            updated_by=creator.id,
        )
        db.add(batch)
        db.flush()

        counts = {"GRADE": len(grades)}
        hashes = {"GRADE": "c" * 64}
        max_ids = {"GRADE": max(int(row.id) for row in grades)}
        reason = "W1 Playwright 正式归档基线"
        payload = manifest_service._manifest_payload(
            batch=batch,
            version_no=1,
            domain_counts=counts,
            domain_hashes=hashes,
            max_ids=max_ids,
            reason=reason,
        )
        manifest = ArchiveManifest(
            tenant_id=TID,
            term_id=term.id,
            version_no=1,
            archive_batch_id=batch.id,
            domain_counts_json=manifest_service._json(counts),
            domain_hashes_json=manifest_service._json(hashes),
            max_ids_json=manifest_service._json(max_ids),
            manifest_hash=manifest_service._hash(payload),
            reason=reason,
            supersedes_id=None,
            archived_at=now,
            archived_by=creator.id,
            created_by=creator.id,
        )
        db.add(manifest)
        db.commit()

        fixture = {
            "tenant": TENANT_CODE,
            "creator": {"username": CREATOR_LOGIN, "password": PASSWORD},
            "reviewer": {"username": REVIEWER_LOGIN, "password": PASSWORD},
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "termId": str(term.id),
            "termCode": TERM_CODE,
            "approvalTargetIds": [str(grades[0].id), str(grades[1].id)],
            "rejectTargetIds": [str(grades[2].id), str(grades[3].id)],
            "manifestV1Id": str(manifest.id),
            "manifestV1Hash": manifest.manifest_hash,
            "creatorUserId": str(creator.id),
            "reviewerUserId": str(reviewer.id),
        }
        FIXTURE_PATH.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[w1-archive-correction-seed] {FIXTURE_PATH}")
        print(json.dumps(fixture, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
