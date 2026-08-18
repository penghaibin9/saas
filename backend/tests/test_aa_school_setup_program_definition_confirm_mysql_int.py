"""INT MySQL contract for the local Program DEFINITION transaction writer."""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

TID = 1000000000000000001


def _service(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_confirm_service as service

    monkeypatch.setattr(service, "_tid", lambda: TID)
    monkeypatch.setattr(core, "_tid", lambda: TID)
    monkeypatch.setattr(
        service,
        "build_affairs_context",
        lambda _user, _db: SimpleNamespace(
            scope_type="TENANT_ALL",
            college_ids=set(),
            class_ids=set(),
        ),
    )
    return service


def _seed_authorities():
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, Major

    suffix = uuid.uuid4().hex[:10].upper()
    db = get_sessionmaker()()
    major = Major(
        tenant_id=TID,
        college_id=880001,
        major_name=f"INT软件技术-{suffix}",
        code=f"PM{suffix}",
        status="ACTIVE",
        education_years=3,
        enroll_status="ENROLLING",
    )
    course = AaCourse(
        tenant_id=TID,
        course_code=f"PC{suffix}",
        course_name=f"INT程序设计-{suffix}",
        category="MAJOR_CORE",
        nature="REQUIRED",
        credit=3,
        exam_mode="EXAM",
        is_core=True,
        prerequisite_codes_json="[]",
        applicable_majors_json="[]",
        is_all_major=False,
        version=1,
        status="ENABLED",
    )
    db.add_all([major, course])
    db.commit()
    result = int(major.id), str(course.course_code), int(course.id)
    db.close()
    return result


def _normalized(major_id: int, course_code: str, series_key: str):
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter

    return adapter.normalize_program_import_rows(
        {
            "MAIN": [
                {
                    "programSeriesKey": series_key,
                    "programVersion": 1,
                    "programName": "INT软件技术2026培养方案",
                    "majorId": major_id,
                    "gradeYear": "2026",
                    "totalCredits": "3",
                    "educationYears": 3,
                }
            ],
            "COURSE": [
                {
                    "programSeriesKey": series_key,
                    "programVersion": 1,
                    "courseCode": course_code,
                    "courseVersion": 1,
                    "openTermNo": 1,
                    "module": "MAJOR_CORE",
                    "formationMode": "ADMIN_FIXED",
                    "creditSnapshot": "",
                }
            ],
            "CREDIT_REQUIREMENT": [
                {
                    "programSeriesKey": series_key,
                    "programVersion": 1,
                    "module": "MAJOR_CORE",
                    "creditTarget": "3",
                }
            ],
            "PRACTICE": [
                {
                    "programSeriesKey": series_key,
                    "programVersion": 1,
                    "segmentName": "综合实训",
                    "segmentType": "COURSE_DESIGN",
                    "openTermNo": 1,
                    "weeks": "1",
                    "credit": "1",
                    "orgMode": "CENTRALIZED",
                    "assessmentMode": "CHECK",
                    "location": "校内实训中心",
                }
            ],
            "GRADUATION": [
                {
                    "programSeriesKey": series_key,
                    "programVersion": 1,
                    "category": "ABILITY",
                    "content": "完成综合项目并通过考核",
                }
            ],
            "BINDING": [
                {
                    "programSeriesKey": series_key,
                    "programVersion": 1,
                    "majorId": major_id,
                    "gradeYear": "2026",
                    "bindingScope": "MAJOR_GRADE",
                    "classId": "",
                }
            ],
        }
    )


@pytest.mark.usefixtures("db_mode")
def test_program_definition_confirm_create_draft_then_repeat_reuse_zero_domain_write(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaProgram,
        AaProgramCourse,
        AaProgramGraduationRequirement,
        AaProgramPracticeSegment,
    )

    service = _service(monkeypatch)
    major_id, course_code, course_id = _seed_authorities()
    series_key = f"INT-SER-{uuid.uuid4().hex[:12].upper()}"
    normalized = _normalized(major_id, course_code, series_key)
    user = {"currentRoleCode": "ACADEMIC_ADMIN"}

    first = service.confirm_program_definition_import(normalized, user=user)
    second = service.confirm_program_definition_import(normalized, user=user)

    assert first["phase"] == "DEFINITION"
    assert first["domainMutationWriteCount"] == 4
    assert len(first["createdProgramIds"]) == 1
    assert first["reconciliation"]["reconciliationSafe"] is True
    assert first["reconciliation"]["importedPrograms"] == 1
    assert first["reconciliation"]["reusedPrograms"] == 0

    assert second["phase"] == "DEFINITION"
    assert second["domainMutationWriteCount"] == 0
    assert second["createdProgramIds"] == []
    assert second["reconciliation"]["reconciliationSafe"] is True
    assert second["reconciliation"]["importedPrograms"] == 0
    assert second["reconciliation"]["reusedPrograms"] == 1

    db = get_sessionmaker()()
    programs = db.scalars(
        select(AaProgram).where(
            AaProgram.tenant_id == TID,
            AaProgram.series_key == series_key,
            AaProgram.version == 1,
            AaProgram.is_deleted.is_(False),
        )
    ).all()
    assert len(programs) == 1
    program = programs[0]
    assert program.status == "DRAFT"
    assert program.prev_version_id is None
    requirement = json.loads(program.requirement_json)
    assert requirement == {
        "creditStructure": [{"creditTarget": "3", "module": "MAJOR_CORE"}]
    }

    relations = db.scalars(
        select(AaProgramCourse).where(
            AaProgramCourse.tenant_id == TID,
            AaProgramCourse.program_id == program.id,
            AaProgramCourse.is_deleted.is_(False),
        )
    ).all()
    practices = db.scalars(
        select(AaProgramPracticeSegment).where(
            AaProgramPracticeSegment.tenant_id == TID,
            AaProgramPracticeSegment.program_id == program.id,
            AaProgramPracticeSegment.is_deleted.is_(False),
        )
    ).all()
    graduations = db.scalars(
        select(AaProgramGraduationRequirement).where(
            AaProgramGraduationRequirement.tenant_id == TID,
            AaProgramGraduationRequirement.program_id == program.id,
            AaProgramGraduationRequirement.is_deleted.is_(False),
        )
    ).all()
    db.close()

    assert len(relations) == 1
    assert relations[0].course_id == course_id
    assert relations[0].formation_mode == "ADMIN_FIXED"
    assert len(practices) == 1
    assert practices[0].status == "ACTIVE"
    assert len(graduations) == 1
    assert graduations[0].status == "ACTIVE"


def test_program_definition_writer_does_not_open_shared_dispatcher_owner():
    import inspect
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_confirm_service as service

    source = inspect.getsource(service)
    assert "data_exchange_confirm_service" not in source
    assert "data_exchange_confirm_legacy" not in source
    assert "academic_file_exchange_service" not in source
    assert "create_new_version" not in source
    assert "status=\"ENABLED\"" not in source
