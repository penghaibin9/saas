#!/usr/bin/env python3
"""Seed one real internship record after the shared full-stack account fixture."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete

from app.db.session import get_sessionmaker
from app.models import InternshipRecord

TENANT_ID = 88101
STUDENT_PROFILE_ID = 88131
TEACHER_ID = 88113
BATCH_ID = 88141
INTERNSHIP_RECORD_ID = 88142


def main() -> None:
    db = get_sessionmaker()()
    try:
        db.execute(delete(InternshipRecord).where(
            InternshipRecord.tenant_id == TENANT_ID,
            InternshipRecord.id == INTERNSHIP_RECORD_ID,
        ))
        record = InternshipRecord(
            id=INTERNSHIP_RECORD_ID,
            tenant_id=TENANT_ID,
            student_id=STUDENT_PROFILE_ID,
            batch_id=BATCH_ID,
            enterprise_name="全栈验收企业",
            position_name="软件测试实习生",
            advisor_name="全栈验收教师",
            enterprise_mentor_name="验收企业导师",
            advisor_user_id=TEACHER_ID,
            eligibility_status="QUALIFIED",
            destination_type="SELF_ARRANGED",
            status="ONBOARD",
            risk_level="NONE",
            intern_start_date=datetime(2026, 9, 1),
            intern_end_date=datetime(2027, 1, 31),
        )
        db.add(record)
        db.commit()
        print({
            "internshipRecordId": record.id,
            "studentProfileId": record.student_id,
            "batchId": record.batch_id,
            "advisorUserId": record.advisor_user_id,
            "status": record.status,
        })
    finally:
        db.close()


if __name__ == "__main__":
    main()
