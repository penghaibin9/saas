"""Prepare isolated AA-004 major-split browser fixture."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import College, Major, SchoolClass, StudentAcademicFact, StudentProfile, Tenant
from app.modules.academic_affairs.services.academic_affairs_student_fact_service import create_baseline_student_academic_fact

TID = 1000000000000000007
TENANT_CODE = "sandbox-school"
STUDENT_NO = "E2E20260001"
GRADE = "2026"
STATE_PATH = Path(__file__).resolve().parents[1] / "tmp/e2e_academic_aa004_state.local.json"


def safe_target() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    if str(os.getenv("APP_ENV") or "").lower() in {"prod", "production"}:
        raise SystemExit("refusing AA-004 fixture in production")
    raw = str(os.getenv("DATABASE_URL") or "")
    lowered = raw.lower()
    if not raw or not any(x in lowered for x in ("e2e", "test")):
        raise SystemExit("AA-004 requires local e2e/test database")
    if urlparse(raw).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("AA-004 fixture only accepts local MySQL")


def one(db, model, **where):
    stmt = select(model)
    for key, value in where.items():
        stmt = stmt.where(getattr(model, key) == value)
    rows = db.scalars(stmt).all()
    if len(rows) != 1:
        raise SystemExit(f"expected one {model.__name__} for {where}, got {len(rows)}")
    return rows[0]


def ensure_major(db, college_id: int, name: str) -> Major:
    row = db.scalars(select(Major).where(
        Major.tenant_id == TID,
        Major.college_id == college_id,
        Major.major_name == name,
        Major.is_deleted.is_(False),
    )).first()
    if row is None:
        row = Major(tenant_id=TID, college_id=college_id, major_name=name, status="ACTIVE")
        db.add(row)
        db.flush()
    row.status = "ACTIVE"
    row.is_deleted = False
    return row


def ensure_source_class(db, source_major_id: int) -> SchoolClass:
    name = "AA-004大类2026验收班"
    row = db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == TID,
        SchoolClass.class_name == name,
        SchoolClass.is_deleted.is_(False),
    )).first()
    if row is None:
        row = SchoolClass(
            tenant_id=TID,
            major_id=source_major_id,
            class_name=name,
            class_code="AA004-SRC-2026",
            grade=GRADE,
            status="ACTIVE",
            class_status="NORMAL",
            capacity=50,
        )
        db.add(row)
        db.flush()
    row.major_id = source_major_id
    row.grade = GRADE
    row.status = "ACTIVE"
    row.class_status = "NORMAL"
    row.is_deleted = False
    return row


def main() -> int:
    safe_target()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TID)
        if not tenant or tenant.tenant_code != TENANT_CODE:
            raise SystemExit("sandbox-school tenant fixture is missing")
        student = one(db, StudentProfile, tenant_id=TID, student_no=STUDENT_NO)
        if not student.college_id:
            raise SystemExit("AA-004 student lacks college identity")
        college = one(db, College, tenant_id=TID, id=int(student.college_id))

        source = ensure_major(db, int(college.id), "AA-004电子信息大类")
        target_a = ensure_major(db, int(college.id), "AA-004软件技术")
        target_b = ensure_major(db, int(college.id), "AA-004网络技术")
        source_class = ensure_source_class(db, int(source.id))

        # Disposable e2e baseline only: align the canonical Stage C1 fact with the browser starting identity.
        student.major_id = int(source.id)
        student.class_id = int(source_class.id)
        student.college_id = int(college.id)
        student.grade = GRADE
        student.student_status = "NORMAL"
        student.status = "ACTIVE"
        student.is_deleted = False
        db.flush()
        db.query(StudentAcademicFact).filter(
            StudentAcademicFact.tenant_id == TID,
            StudentAcademicFact.student_id == int(student.id),
        ).delete(synchronize_session=False)
        baseline = create_baseline_student_academic_fact(
            db,
            student,
            valid_from=datetime.utcnow() - timedelta(minutes=5),
            source_type="E2E_AA004_BASELINE",
            source_quality="EXACT",
            tenant_id=TID,
        )
        db.commit()
        db.refresh(student)

        state = {
            "tenantId": str(TID),
            "tenantCode": TENANT_CODE,
            "studentId": str(student.id),
            "studentNo": student.student_no,
            "studentName": student.real_name,
            "grade": GRADE,
            "collegeId": str(college.id),
            "sourceMajorId": str(source.id),
            "sourceMajorName": source.major_name,
            "sourceClassId": str(source_class.id),
            "targetMajorAId": str(target_a.id),
            "targetMajorAName": target_a.major_name,
            "targetMajorBId": str(target_b.id),
            "targetMajorBName": target_b.major_name,
            "baselineFactId": str(baseline.id),
            "baselineFactVersion": int(baseline.version_no),
            "studentBaseVersion": int(student.version or 0),
        }
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
