"""Stage C1 program-transition assessment contracts."""
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
    set_tenant({"tenantId": str(TID), "tenantCode": "stage-c1-program"})


def _seed_student_and_majors(db):
    from app.models import College, Major, SchoolClass, StudentProfile

    college = College(tenant_id=TID, college_name="C1学院", status="ACTIVE")
    db.add(college); db.flush()
    source = Major(tenant_id=TID, college_id=college.id, major_name="源专业", status="ACTIVE")
    target = Major(tenant_id=TID, college_id=college.id, major_name="目标专业", status="ACTIVE")
    db.add_all([source, target]); db.flush()
    source_class = SchoolClass(
        tenant_id=TID, major_id=source.id, class_name="源2401", class_code="C1-SRC",
        grade="2024", status="ACTIVE", class_status="NORMAL",
    )
    target_class = SchoolClass(
        tenant_id=TID, major_id=target.id, class_name="目2401", class_code="C1-TGT",
        grade="2024", status="ACTIVE", class_status="NORMAL",
    )
    db.add_all([source_class, target_class]); db.flush()
    student = StudentProfile(
        tenant_id=TID, student_no=f"C1PT-{source.id}", real_name="方案迁移学生",
        college_id=college.id, major_id=source.id, class_id=source_class.id, grade="2024",
        current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
        created_at=datetime.utcnow() - timedelta(days=30),
    )
    db.add(student); db.flush()
    return student, source, target, source_class, target_class


def _add_program_binding(db, *, major, grade="2024", class_id=None, name="方案", version=1):
    from app.models import AaProgram, AaProgramBinding

    program = AaProgram(
        tenant_id=TID, program_name=name, major_id=major.id, grade_year=grade,
        version=version, status="PUBLISHED",
    )
    db.add(program); db.flush()
    binding = AaProgramBinding(
        tenant_id=TID, program_id=program.id, major_id=major.id,
        grade_year=grade, class_id=class_id, bound_at=datetime.utcnow(), status="ACTIVE",
    )
    db.add(binding); db.flush()
    return program, binding


@pytest.mark.usefixtures("db_mode")
def test_unique_target_binding_is_assessed_and_marked_applied():
    from app.models.academic_affairs_program_transition import ProgramTransitionAssessment

    _activate()
    db = get_sessionmaker()()
    try:
        student, source, target, _source_class, target_class = _seed_student_and_majors(db)
        source_program, _ = _add_program_binding(db, major=source, name="源方案")
        target_program, _ = _add_program_binding(
            db, major=target, class_id=target_class.id, name="目标班级方案"
        )
        base_version = int(student.version or 0)

        fact, _projected = append_student_academic_fact(
            db,
            student.id,
            effective_at=datetime.utcnow(),
            college_id=target.college_id,
            major_id=target.id,
            class_id=target_class.id,
            source_type="TRANSFER_MAJOR",
            source_ref_id=88001,
            expected_student_version=base_version,
        )
        db.commit()

        row = db.query(ProgramTransitionAssessment).filter(
            ProgramTransitionAssessment.tenant_id == TID,
            ProgramTransitionAssessment.student_id == student.id,
            ProgramTransitionAssessment.source_ref_id == 88001,
        ).one()
        assert row.from_program_id == source_program.id
        assert row.target_program_id == target_program.id
        assert row.decision == "SWITCH_TARGET"
        assert row.assessment_status == "APPLIED"
        assert row.applied_fact_id == fact.id
        assert row.source_fact_version == 1
    finally:
        db.close()
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_missing_target_binding_never_guesses_program_and_records_review_debt():
    from app.models.academic_affairs_program_transition import ProgramTransitionAssessment

    _activate()
    db = get_sessionmaker()()
    try:
        student, source, target, _source_class, target_class = _seed_student_and_majors(db)
        _add_program_binding(db, major=source, name="源方案")
        append_student_academic_fact(
            db,
            student.id,
            effective_at=datetime.utcnow(),
            college_id=target.college_id,
            major_id=target.id,
            class_id=target_class.id,
            source_type="MAJOR_SPLIT",
            source_ref_id=88002,
            expected_student_version=int(student.version or 0),
        )
        db.commit()

        row = db.query(ProgramTransitionAssessment).filter(
            ProgramTransitionAssessment.tenant_id == TID,
            ProgramTransitionAssessment.student_id == student.id,
            ProgramTransitionAssessment.source_ref_id == 88002,
        ).one()
        assert row.target_program_id is None
        assert row.decision == "MANUAL_REVIEW"
        assert row.assessment_status == "APPLIED_REVIEW_REQUIRED"
        assert '"resolution": "NONE"' in row.evidence_json
    finally:
        db.close()
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_same_score_multiple_target_programs_are_ambiguous_not_arbitrarily_selected():
    from app.models.academic_affairs_program_transition import ProgramTransitionAssessment

    _activate()
    db = get_sessionmaker()()
    try:
        student, source, target, _source_class, target_class = _seed_student_and_majors(db)
        _add_program_binding(db, major=source, name="源方案")
        _add_program_binding(db, major=target, grade="2024", name="目标方案A")
        _add_program_binding(db, major=target, grade="2024", name="目标方案B")
        append_student_academic_fact(
            db,
            student.id,
            effective_at=datetime.utcnow(),
            college_id=target.college_id,
            major_id=target.id,
            class_id=target_class.id,
            source_type="TRANSFER_MAJOR",
            source_ref_id=88003,
            expected_student_version=int(student.version or 0),
        )
        db.commit()

        row = db.query(ProgramTransitionAssessment).filter(
            ProgramTransitionAssessment.tenant_id == TID,
            ProgramTransitionAssessment.student_id == student.id,
            ProgramTransitionAssessment.source_ref_id == 88003,
        ).one()
        assert row.target_program_id is None
        assert row.decision == "MANUAL_REVIEW"
        assert row.assessment_status == "APPLIED_REVIEW_REQUIRED"
        assert '"resolution": "AMBIGUOUS"' in row.evidence_json
    finally:
        db.close()
        set_tenant(None)
