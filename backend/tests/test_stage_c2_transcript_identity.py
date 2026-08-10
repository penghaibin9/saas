"""Stage C2 transcript historical-identity production contracts."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.core.context import set_tenant
from app.db.session import get_sessionmaker

TID = 98111


def _activate():
    set_tenant({"tenantId": str(TID), "tenantCode": "stage-c2-transcript"})


@pytest.mark.usefixtures("db_mode")
def test_term_transcript_identity_uses_fact_at_term_start_not_current_profile():
    from app.models import AaTerm, StudentProfile
    from app.models.academic_affairs_student_fact import StudentAcademicFact
    from app.modules.academic_affairs.services.academic_affairs_transcript_historical_facade import (
        attach_historical_identities,
    )

    _activate()
    db = get_sessionmaker()()
    try:
        created_at = datetime(2025, 8, 20, 8, 0, 0)
        term_start = datetime(2025, 9, 1, 0, 0, 0)
        transfer_at = datetime(2026, 2, 1, 0, 0, 0)
        student = StudentProfile(
            tenant_id=TID,
            student_no="C2TR001",
            real_name="C2 transcript",
            college_id=11,
            major_id=101,
            class_id=1001,
            grade="2025",
            current_stage="ON_CAMPUS",
            student_status="REGISTERED",
            status="ACTIVE",
            created_at=created_at,
        )
        db.add(student)
        db.flush()
        base = db.query(StudentAcademicFact).filter(
            StudentAcademicFact.tenant_id == TID,
            StudentAcademicFact.student_id == student.id,
            StudentAcademicFact.version_no == 1,
        ).one()
        base.valid_to = transfer_at
        db.add(StudentAcademicFact(
            tenant_id=TID,
            student_id=student.id,
            version_no=2,
            valid_from=transfer_at,
            valid_to=None,
            student_status="REGISTERED",
            college_id=22,
            major_id=202,
            class_id=2002,
            grade="2025",
            source_type="TEST_TRANSFER_MAJOR",
            source_quality="EXACT",
        ))
        # Simulate today's projection after the transfer. Historical transcript logic
        # must not read these current values for the earlier term.
        student.college_id = 22
        student.major_id = 202
        student.class_id = 2002
        db.add(AaTerm(
            tenant_id=TID,
            year_code="2025-2026",
            term_no=1,
            term_name="2025-2026 第一学期",
            start_date=term_start,
            status="ARCHIVED",
        ))
        db.commit()

        payload = attach_historical_identities(
            db,
            student.id,
            {"items": [{"gradeId": "1", "term": "2025-2026-1", "courseName": "数据结构"}]},
        )
        identity = payload["items"][0]["academicIdentity"]
        assert identity["status"] == "RESOLVED"
        assert identity["majorId"] == "101"
        assert identity["collegeId"] == "11"
        assert identity["classId"] == "1001"
        assert identity["asOf"] == term_start.isoformat()
        assert payload["identityPolicy"] == "TERM_START_ACADEMIC_FACT_V1"
        assert payload["cumulativeHeaderIdentity"] is None
        assert payload["cumulativeHeaderIdentityPolicy"] == "NO_IMPLICIT_CURRENT_PROFILE"
        assert payload["historicalIdentityComplete"] is True
        assert student.major_id == 202
    finally:
        db.close()
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_transcript_missing_term_metadata_never_falls_back_to_current_profile():
    from app.models import StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_transcript_historical_facade import (
        attach_historical_identities,
    )

    _activate()
    db = get_sessionmaker()()
    try:
        student = StudentProfile(
            tenant_id=TID,
            student_no="C2TR002",
            real_name="C2 transcript missing term",
            college_id=99,
            major_id=909,
            class_id=9009,
            grade="2025",
            current_stage="ON_CAMPUS",
            student_status="REGISTERED",
            status="ACTIVE",
        )
        db.add(student)
        db.commit()
        db.refresh(student)

        payload = attach_historical_identities(
            db,
            student.id,
            {"items": [{"gradeId": "2", "term": "LEGACY-UNKNOWN", "courseName": "历史课程"}]},
        )
        identity = payload["items"][0]["academicIdentity"]
        assert identity["status"] == "UNKNOWN"
        assert identity["reason"] in {"TERM_CODE_INVALID", "TERM_NOT_FOUND"}
        assert "majorId" not in identity
        assert "collegeId" not in identity
        assert "classId" not in identity
        assert payload["historicalIdentityComplete"] is False
    finally:
        db.close()
        set_tenant(None)
