"""Seed IX-011 prerequisites only: real internship context + enabled agreement template.

No InternshipAgreement row is created here. The agreement lifecycle itself must be
produced by visible browser interactions in the dedicated IX-011 Playwright gate.
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import InternshipAgreement, InternshipAgreementTemplate
from e2e_seed_internship_sandbox import (
    assert_safe_target,
    ensure_batch,
    ensure_company,
    ensure_position,
    ensure_record,
    require_mentor,
    require_student,
    require_tenant,
    run_id,
)

DEFAULT_FIXTURE_PATH = "../e2e/runtime/internship-agreement-fixture.json"
# A real, valid 1x1 PNG. It represents the signed paper scan uploaded through the
# same file input a school operator uses; the file center, not the seed, creates
# the FileObject when the browser uploads it.
SIGNED_SCAN_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "/w8AAusB9Y9Z8WQAAAAASUVORK5CYII="
)


def fixture_path() -> Path:
    return Path(os.getenv("E2E_IX011_FIXTURE_FILE") or DEFAULT_FIXTURE_PATH).resolve()


def ensure_template(db, *, rid: str, batch_id: int, now: datetime) -> InternshipAgreementTemplate:
    name = f"IX011三方协议模板{rid}"
    template = db.scalar(
        select(InternshipAgreementTemplate).where(
            InternshipAgreementTemplate.tenant_id == 1000000000000000007,
            InternshipAgreementTemplate.name == name,
            InternshipAgreementTemplate.is_deleted.is_(False),
        )
    )
    body = (
        "岗位实习三方协议（IX-011 Browser First）\n"
        "甲方（学校）：{{schoolName}}\n"
        "乙方（企业）：{{companyName}}\n"
        "丙方（学生）：{{studentName}}（{{studentNo}}）\n"
        "实习岗位：{{positionName}}\n"
        "校内指导教师：{{teacherName}}\n"
        "实习期间：{{internPeriod}}\n"
        "本协议以学生确认、企业纸质签署扫描件、学校终审为生效证据。"
    )
    if template is None:
        template = InternshipAgreementTemplate(
            tenant_id=1000000000000000007,
            name=name,
            category="STANDARD",
            template_version="ix011-v1",
            body=body,
            variables=[
                {"key": "schoolName", "label": "学校名称"},
                {"key": "companyName", "label": "企业名称"},
                {"key": "studentName", "label": "学生姓名"},
                {"key": "studentNo", "label": "学号"},
                {"key": "positionName", "label": "岗位名称"},
                {"key": "teacherName", "label": "指导教师"},
                {"key": "internPeriod", "label": "实习期间"},
            ],
            scope_batch_ids=[str(batch_id)],
            status="ENABLED",
            is_default=True,
            enabled_at=now,
            remark="IX-011 isolated Browser First prerequisite only",
        )
        db.add(template)
        db.flush()
    else:
        template.body = body
        template.scope_batch_ids = [str(batch_id)]
        template.status = "ENABLED"
        template.is_default = True
        template.enabled_at = now
        template.is_deleted = False
    return template


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

        # IX-011 starts before onboarding. Do not let the generic leave-E2E fixture's
        # display-only "agreement already effective" text fake agreement truth.
        record.status = "READY"
        record.agreement_info = None
        template = ensure_template(db, rid=rid, batch_id=int(batch.id), now=now)

        existing = db.scalars(
            select(InternshipAgreement).where(
                InternshipAgreement.tenant_id == 1000000000000000007,
                InternshipAgreement.internship_id == record.id,
                InternshipAgreement.is_deleted.is_(False),
            )
        ).all()
        if existing:
            raise SystemExit("IX-011 seed must not pre-create agreement business rows")

        db.commit()

        target = fixture_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        scan_path = target.parent / f"ix011-signed-agreement-{rid}.png"
        scan_path.write_bytes(base64.b64decode(SIGNED_SCAN_PNG))
        payload = {
            "runId": rid,
            "tenantCode": "sandbox-school",
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
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
            "templateId": str(template.id),
            "templateName": template.name,
            "scanPath": str(scan_path),
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[e2e-ix011-seed] ready:", json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
