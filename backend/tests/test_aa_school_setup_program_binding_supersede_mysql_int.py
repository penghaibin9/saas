"""INT MySQL supersede history contract for Program BINDING confirmation."""
from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select

TID = 1000000000000000001


def _services(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_authority_service as definition_authority
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_confirm_service as definition_writer
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_confirm_service as binding_writer

    for module in (definition_authority, definition_writer, binding_writer, core):
        monkeypatch.setattr(module, "_tid", lambda: TID)
    context = lambda _user, _db: SimpleNamespace(  # noqa: E731
        scope_type="TENANT_ALL",
        college_ids=set(),
        class_ids=set(),
    )
    monkeypatch.setattr(definition_writer, "build_affairs_context", context)
    monkeypatch.setattr(binding_writer, "build_affairs_context", context)
    return definition_authority, binding_writer


def _seed():
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, Major, Tenant

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8].upper()
    if db.get(Tenant, TID) is None:
        db.add(Tenant(
            id=TID,
            tenant_code=f"int-supersede-{suffix.lower()}",
            school_name=f"INT绑定替换学校-{suffix}",
            status="ACTIVE",
        ))
        db.flush()
    major = Major(
        tenant_id=TID,
        college_id=880001,
        major_name=f"INT软件技术-{suffix}",
        code=f"SM{suffix}",
        status="ACTIVE",
        education_years=3,
        enroll_status="ENROLLING",
    )
    course = AaCourse(
        tenant_id=TID,
        course_code=f"SC{suffix}",
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
    result = int(major.id), str(course.course_code)
    db.close()
    return result


def _rows(*, version: int, major_id: int, course_code: str, series_key: str):
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter

    return adapter.normalize_program_import_rows({
        "MAIN": [{
            "programSeriesKey": series_key,
            "programVersion": version,
            "programName": f"INT软件技术培养方案V{version}",
            "majorId": major_id,
            "gradeYear": "2026",
            "totalCredits": "3",
            "educationYears": 3,
        }],
        "COURSE": [{
            "programSeriesKey": series_key,
            "programVersion": version,
            "courseCode": course_code,
            "courseVersion": 1,
            "openTermNo": 1,
            "module": "MAJOR_CORE",
            "formationMode": "ADMIN_FIXED",
            "creditSnapshot": "",
        }],
        "CREDIT_REQUIREMENT": [{
            "programSeriesKey": series_key,
            "programVersion": version,
            "module": "MAJOR_CORE",
            "creditTarget": "3",
        }],
        "GRADUATION": [{
            "programSeriesKey": series_key,
            "programVersion": version,
            "category": "ABILITY",
            "content": "完成专业综合项目并通过考核",
        }],
        "BINDING": [{
            "programSeriesKey": series_key,
            "programVersion": version,
            "majorId": major_id,
            "gradeYear": "2026",
            "bindingScope": "MAJOR_GRADE",
            "classId": "",
        }],
    })


def _publish(program_id: int):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram

    db = get_sessionmaker()()
    program = db.get(AaProgram, program_id)
    assert program is not None and program.status == "DRAFT"
    program.status = "PUBLISHED"
    db.commit()
    db.close()


@pytest.mark.usefixtures("db_mode")
def test_v2_binding_supersedes_v1_active_without_deleting_history(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramBinding

    definition_authority, binding_writer = _services(monkeypatch)
    major_id, course_code = _seed()
    series_key = f"INT-SUPER-{uuid.uuid4().hex[:12].upper()}"
    user = {"currentRoleCode": "ACADEMIC_ADMIN"}

    v1_rows = _rows(version=1, major_id=major_id, course_code=course_code, series_key=series_key)
    v1_definition = definition_authority.confirm_program_definition_import(v1_rows, user=user)
    v1_id = int(v1_definition["createdProgramIds"][0])
    _publish(v1_id)
    v1_binding = binding_writer.confirm_program_binding_import(v1_rows, user=user)
    assert v1_binding["domainMutationWriteCount"] == 3

    v2_rows = _rows(version=2, major_id=major_id, course_code=course_code, series_key=series_key)
    v2_definition = definition_authority.confirm_program_definition_import(v2_rows, user=user)
    assert v2_definition["reconciliation"]["items"][0]["relationship"] == {
        "prevProgramId": str(v1_id),
        "expectedPrevProgramId": str(v1_id),
    }
    v2_id = int(v2_definition["createdProgramIds"][0])
    _publish(v2_id)

    result = binding_writer.confirm_program_binding_import(v2_rows, user=user)
    assert result["domainMutationWriteCount"] == 4
    assert result["reconciliation"]["reconciliationSafe"] is True
    assert result["reconciliation"]["createdBindings"] == 1
    item = result["reconciliation"]["items"][0]
    assert item["activeRelationshipMatch"] is True
    assert item["supersedeRelationshipMatch"] is True
    assert item["targetStatusMatch"] is True

    db = get_sessionmaker()()
    v1 = db.get(AaProgram, v1_id)
    v2 = db.get(AaProgram, v2_id)
    bindings = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == TID,
        AaProgramBinding.major_id == major_id,
        AaProgramBinding.grade_year == "2026",
        AaProgramBinding.class_id.is_(None),
        AaProgramBinding.is_deleted.is_(False),
    ).order_by(AaProgramBinding.id)).all()
    db.close()

    assert v1 is not None and v1.status == "ENABLED"
    assert v2 is not None and v2.status == "ENABLED"
    assert [(row.program_id, row.status) for row in bindings] == [
        (v1_id, "SUPERSEDED"),
        (v2_id, "ACTIVE"),
    ]
