"""Seed only internship prerequisites for the Playwright leave lifecycle.

The script inserts a batch, company, position, student internship record and mentor
binding into the isolated sandbox-school E2E database.  It deliberately does not
create InternshipLeave or leave audit rows: submit, approve and return transitions
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
    EmpCompany,
    InternshipBatch,
    InternshipPosition,
    InternshipRecord,
    StudentProfile,
    Tenant,
    User,
)

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"
STUDENT_NO = "E2E20260001"
MENTOR_LOGIN = "e2e_advisor_a"
DEFAULT_FIXTURE_PATH = "../e2e/runtime/internship-fixture.json"


def assert_safe_target() -> None:
    env_name = str(os.getenv("APP_ENV") or "").lower()
    deploy_mode = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env_name in {"prod", "production"} or deploy_mode in {"prod", "production"}:
        raise SystemExit("refusing to seed internship E2E prerequisites in production")
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
        raise SystemExit("internship E2E seed only accepts a local database")


def run_id() -> str:
    raw = os.getenv("GITHUB_RUN_ID") or str(int(datetime.utcnow().timestamp() * 1000))
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    return (digits[-12:] or str(int(datetime.utcnow().timestamp())))


def fixture_path() -> Path:
    return Path(os.getenv("E2E_INTERNSHIP_FIXTURE_FILE") or DEFAULT_FIXTURE_PATH).resolve()


def require_tenant(db) -> Tenant:
    tenant = db.get(Tenant, TENANT_ID)
    if tenant is None or tenant.is_deleted:
        raise SystemExit(
            f"tenant {TENANT_CODE}/{TENANT_ID} is missing; run the E2E tenant bootstrap first"
        )
    if tenant.tenant_code != TENANT_CODE:
        raise SystemExit(
            f"tenant id {TENANT_ID} belongs to {tenant.tenant_code!r}, refusing internship E2E seed"
        )
    if tenant.status != "ACTIVE":
        raise SystemExit(
            f"tenant {TENANT_CODE}/{TENANT_ID} is not active, refusing internship E2E seed"
        )
    return tenant


def require_student(db) -> StudentProfile:
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
    return student


def require_mentor(db) -> User:
    mentor = db.scalars(
        select(User).where(
            User.tenant_id == TENANT_ID,
            User.login_name == MENTOR_LOGIN,
            User.is_deleted.is_(False),
        )
    ).first()
    if mentor is None:
        raise SystemExit(
            f"mentor {TENANT_CODE}/{MENTOR_LOGIN} is missing; run the E2E identity bootstrap first"
        )
    return mentor


def ensure_batch(db, rid: str, now: datetime) -> InternshipBatch:
    batch_no = f"PW-INT-E2E-{rid}"
    batch = db.scalars(
        select(InternshipBatch).where(
            InternshipBatch.tenant_id == TENANT_ID,
            InternshipBatch.batch_no == batch_no,
            InternshipBatch.is_deleted.is_(False),
        )
    ).first()
    if batch is None:
        year = now.year
        batch = InternshipBatch(
            tenant_id=TENANT_ID,
            batch_name=f"Playwright 岗位实习交互测试 {rid}",
            batch_no=batch_no,
            academic_year=f"{year}-{year + 1}",
            term="第一学期",
            start_date=now - timedelta(days=30),
            end_date=now + timedelta(days=90),
            signup_start_date=now - timedelta(days=45),
            signup_end_date=now + timedelta(days=30),
            planned_count=1,
            status="RUNNING",
            stage_config=[],
            rules_config={"checkin": {}, "weeklyReport": {}, "guidance": {}, "evaluation": {}, "score": {}},
            remark="Only for isolated Playwright E2E database",
        )
        db.add(batch)
        db.flush()
    else:
        batch.status = "RUNNING"
        batch.start_date = now - timedelta(days=30)
        batch.end_date = now + timedelta(days=90)
        batch.is_deleted = False
    return batch


def ensure_company(db, rid: str) -> EmpCompany:
    credit_code = f"PW-E2E-{rid}"
    company = db.scalars(
        select(EmpCompany).where(
            EmpCompany.tenant_id == TENANT_ID,
            EmpCompany.credit_code == credit_code,
            EmpCompany.is_deleted.is_(False),
        )
    ).first()
    if company is None:
        company = EmpCompany(
            tenant_id=TENANT_ID,
            name=f"Playwright 智能科技有限公司 {rid}",
            credit_code=credit_code,
            industry="软件和信息技术服务业",
            nature="民营企业",
            city="长沙",
            region="湖南省长沙市",
            address="岳麓区测试产业园 8 号楼",
            scale="中型",
            contact_person="周工",
            cooperation_level="核心合作",
            source="SCHOOL_ENTERPRISE",
            coop_status="ACTIVE",
            qualification_status="PASSED",
            status="ACTIVE",
        )
        db.add(company)
        db.flush()
    return company


def ensure_position(db, rid: str, batch: InternshipBatch, company: EmpCompany, now: datetime) -> InternshipPosition:
    title = f"软件测试实习生 {rid}"
    position = db.scalars(
        select(InternshipPosition).where(
            InternshipPosition.tenant_id == TENANT_ID,
            InternshipPosition.batch_id == batch.id,
            InternshipPosition.title == title,
            InternshipPosition.is_deleted.is_(False),
        )
    ).first()
    if position is None:
        position = InternshipPosition(
            tenant_id=TENANT_ID,
            company_id=company.id,
            company_name=company.name,
            batch_id=batch.id,
            title=title,
            category="软件测试",
            major_requirement="软件技术/计算机应用",
            grade_requirement=f"{now.year + 1}届",
            work_location="长沙市岳麓区",
            salary_range="3500-5000元/月",
            subsidy="餐补+交通补贴",
            headcount=1,
            allocated_count=1,
            mentor_name="周工",
            status="PUBLISHED",
            publish_at=now,
        )
        db.add(position)
        db.flush()
    return position


def ensure_record(
    db,
    student: StudentProfile,
    mentor: User,
    batch: InternshipBatch,
    company: EmpCompany,
    position: InternshipPosition,
    now: datetime,
) -> InternshipRecord:
    record = db.scalars(
        select(InternshipRecord).where(
            InternshipRecord.tenant_id == TENANT_ID,
            InternshipRecord.student_id == student.id,
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
        )
    ).first()
    values = {
        "enterprise_name": company.name,
        "position_name": position.title,
        "advisor_name": mentor.real_name,
        "advisor_user_id": mentor.id,
        "enterprise_mentor_name": "周工",
        "enterprise_id": company.id,
        "position_id": position.id,
        "eligibility_status": "QUALIFIED",
        "destination_type": "ASSIGNED",
        "status": "ONBOARD",
        "risk_level": "NONE",
        "intern_start_date": now - timedelta(days=30),
        "intern_end_date": now + timedelta(days=90),
        "insurance_info": "Playwright E2E 实习责任险",
        "agreement_info": "Playwright E2E 三方协议已生效",
        "remark": "Browser E2E prerequisites only; leave state is created by UI",
    }
    if record is None:
        record = InternshipRecord(
            tenant_id=TENANT_ID,
            student_id=student.id,
            batch_id=batch.id,
            **values,
        )
        db.add(record)
        db.flush()
    else:
        for key, value in values.items():
            setattr(record, key, value)
        record.is_deleted = False
    return record


def main() -> int:
    assert_safe_target()
    rid = run_id()
    now = datetime.utcnow()
    db = get_sessionmaker()()
    try:
        require_tenant(db)
        student = require_student(db)
        mentor = require_mentor(db)
        batch = ensure_batch(db, rid, now)
        company = ensure_company(db, rid)
        position = ensure_position(db, rid, batch, company, now)
        record = ensure_record(db, student, mentor, batch, company, position, now)
        db.commit()

        payload = {
            "runId": rid,
            "tenantCode": TENANT_CODE,
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "batchNo": batch.batch_no,
            "internshipId": str(record.id),
            "studentId": str(student.id),
            "studentNo": student.student_no,
            "studentName": student.real_name,
            "mentorUserId": str(mentor.id),
            "mentorLogin": mentor.login_name,
            "mentorName": mentor.real_name,
            "companyId": str(company.id),
            "companyName": company.name,
            "positionId": str(position.id),
            "positionName": position.title,
        }
        target = fixture_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[e2e-internship-seed] ready:", json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
