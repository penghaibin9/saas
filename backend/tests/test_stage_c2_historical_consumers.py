"""Stage C2: historical consumers must read StudentAcademicFact, not current StudentProfile."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.context import set_tenant
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
    append_student_academic_fact,
)

TID = 98110


def _activate():
    set_tenant({"tenantId": str(TID), "tenantCode": "stage-c2"})


def _student(no: str, *, created_at: datetime):
    from app.models import StudentProfile

    return StudentProfile(
        tenant_id=TID,
        student_no=no,
        real_name=f"C2-{no}",
        college_id=11,
        major_id=101,
        class_id=1001,
        grade="2024",
        current_stage="ON_CAMPUS",
        student_status="REGISTERED",
        status="ACTIVE",
        created_at=created_at,
    )


@pytest.mark.usefixtures("db_mode")
def test_selection_identity_uses_fact_at_effective_time_after_later_transfer():
    from app.modules.academic_affairs.services.academic_affairs_selection_final_service import (
        _selection_academic_identity,
    )

    _activate()
    db = get_sessionmaker()()
    try:
        now = datetime.utcnow()
        created_at = now - timedelta(days=90)
        transfer_at = now - timedelta(days=30)
        student = _student("C2SEL001", created_at=created_at)
        db.add(student)
        db.flush()
        base_version = int(student.version or 0)

        append_student_academic_fact(
            db,
            student.id,
            effective_at=transfer_at,
            major_id=202,
            class_id=2002,
            source_type="TRANSFER_MAJOR",
            source_ref_id=82001,
            expected_student_version=base_version,
        )
        db.commit()
        db.refresh(student)
        assert student.major_id == 202 and student.class_id == 2002

        historical, old_fact = _selection_academic_identity(
            db,
            student,
            effective_at=now - timedelta(days=60),
        )
        current, current_fact = _selection_academic_identity(
            db,
            student,
            effective_at=now - timedelta(days=10),
        )

        assert historical.major_id == 101 and historical.class_id == 1001
        assert current.major_id == 202 and current.class_id == 2002
        assert old_fact.id != current_fact.id
    finally:
        db.close()
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_program_resolution_as_of_uses_old_fact_not_current_profile():
    from app.models import AaProgram, AaProgramBinding
    from app.modules.academic_affairs.services.student_program_resolution_service import (
        resolve_student_program_at,
    )

    _activate()
    db = get_sessionmaker()()
    try:
        now = datetime.utcnow()
        created_at = now - timedelta(days=120)
        transfer_at = now - timedelta(days=30)
        student = _student("C2PROG001", created_at=created_at)
        db.add(student)
        db.flush()

        old_program = AaProgram(
            tenant_id=TID,
            program_name="C2 old major program",
            major_id=101,
            grade_year="2024",
            total_credits=120,
            version=1,
            status="FROZEN",
        )
        new_program = AaProgram(
            tenant_id=TID,
            program_name="C2 new major program",
            major_id=202,
            grade_year="2024",
            total_credits=130,
            version=1,
            status="ENABLED",
        )
        db.add_all([old_program, new_program])
        db.flush()
        db.add_all([
            AaProgramBinding(
                tenant_id=TID,
                program_id=old_program.id,
                major_id=101,
                grade_year="2024",
                class_id=1001,
                bound_at=created_at,
                status="SUPERSEDED",
            ),
            AaProgramBinding(
                tenant_id=TID,
                program_id=new_program.id,
                major_id=202,
                grade_year="2024",
                class_id=2002,
                bound_at=transfer_at,
                status="ACTIVE",
            ),
        ])
        db.flush()

        append_student_academic_fact(
            db,
            student.id,
            effective_at=transfer_at,
            major_id=202,
            class_id=2002,
            source_type="TRANSFER_MAJOR",
            source_ref_id=82002,
            expected_student_version=int(student.version or 0),
        )
        db.commit()
        db.refresh(student)
        assert student.major_id == 202

        historical = resolve_student_program_at(
            db,
            student,
            tenant_id=TID,
            as_of=now - timedelta(days=60),
        )
        current = resolve_student_program_at(
            db,
            student,
            tenant_id=TID,
            as_of=now - timedelta(days=10),
        )

        assert historical.status == "RESOLVED"
        assert historical.program.id == old_program.id
        assert historical.rule == "CLASS_HISTORICAL_EFFECTIVE"
        assert current.status == "RESOLVED"
        assert current.program.id == new_program.id
        assert current.rule == "CLASS_BINDING"
    finally:
        db.close()
        set_tenant(None)
