"""INT MySQL contract for ordinary Program BINDING confirmation."""
from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select

TID = 1000000000000000001


def _patch_services(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_authority_service as definition_authority
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_confirm_service as definition_writer
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_confirm_service as binding_writer

    monkeypatch.setattr(definition_authority, "_tid", lambda: TID)
    monkeypatch.setattr(definition_writer, "_tid", lambda: TID)
    monkeypatch.setattr(binding_writer, "_tid", lambda: TID)
    monkeypatch.setattr(core, "_tid", lambda: TID)
    context = lambda _user, _db: SimpleNamespace(  # noqa: E731 - compact test authority
        scope_type="TENANT_ALL",
        college_ids=set(),
        class_ids=set(),
    )
    monkeypatch.setattr(definition_writer, "build_affairs_context", context)
    monkeypatch.setattr(binding_writer, "build_affairs_context", context)
    return definition_authority, binding_writer


def _seed_authorities():
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, Major, Tenant

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8].upper()
    if db.get(Tenant, TID) is None:
        db.add(Tenant(
            id=TID,
            tenant_code=f"int-binding-{suffix.lower()}",
            school_name=f"INT培养方案绑定学校-{suffix}",
            status="ACTIVE",
        ))
        db.flush()
    major = Major(
        tenant_id=TID,
        college_id=880001,
        major_name=f"INT软件技术-{suffix}",
        code=f"BM{suffix}",
        status="ACTIVE",
        education_years=3,
        enroll_status="ENROLLING",
    )
    course = AaCourse(
        tenant_id=TID,
        course_code=f"BC{suffix}",
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


def _normalized(*, major_id: int, course_code: str, series_key: str):
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter

    return adapter.normalize_program_import_rows({
        "MAIN": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "programName": "INT软件技术2026培养方案",
            "majorId": major_id,
            "gradeYear": "2026",
            "totalCredits": "3",
            "educationYears": 3,
        }],
        "COURSE": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "courseCode": course_code,
            "courseVersion": 1,
            "openTermNo": 1,
            "module": "MAJOR_CORE",
            "formationMode": "ADMIN_FIXED",
            "creditSnapshot": "",
        }],
        "CREDIT_REQUIREMENT": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "module": "MAJOR_CORE",
            "creditTarget": "3",
        }],
        "GRADUATION": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "category": "ABILITY",
            "content": "完成专业综合项目并通过考核",
        }],
        "BINDING": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "majorId": major_id,
            "gradeYear": "2026",
            "bindingScope": "MAJOR_GRADE",
            "classId": "",
        }],
    })


@pytest.mark.usefixtures("db_mode")
def test_binding_confirm_requires_published_definition_then_create_and_repeat_reuse_zero_write(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramBinding

    definition_authority, binding_writer = _patch_services(monkeypatch)
    major_id, course_code = _seed_authorities()
    series_key = f"INT-BIND-{uuid.uuid4().hex[:12].upper()}"
    rows = _normalized(major_id=major_id, course_code=course_code, series_key=series_key)
    user = {"currentRoleCode": "ACADEMIC_ADMIN"}

    definition = definition_authority.confirm_program_definition_import(rows, user=user)
    assert definition["domainMutationWriteCount"] == 3  # Program + Course + Graduation
    program_id = int(definition["createdProgramIds"][0])

    db = get_sessionmaker()()
    program = db.get(AaProgram, program_id)
    assert program is not None
    assert program.status == "DRAFT"
    program.status = "PUBLISHED"  # explicit approval boundary, outside ordinary import
    db.commit()
    db.close()

    first = binding_writer.confirm_program_binding_import(rows, user=user)
    second = binding_writer.confirm_program_binding_import(rows, user=user)

    assert first["phase"] == "BINDING"
    assert first["domainMutationWriteCount"] == 3
    assert first["reconciliation"]["reconciliationSafe"] is True
    assert first["reconciliation"]["createdBindings"] == 1
    assert first["reconciliation"]["reusedBindings"] == 0

    assert second["domainMutationWriteCount"] == 0
    assert second["reconciliation"]["reconciliationSafe"] is True
    assert second["reconciliation"]["createdBindings"] == 0
    assert second["reconciliation"]["reusedBindings"] == 1

    db = get_sessionmaker()()
    program = db.get(AaProgram, program_id)
    bindings = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == TID,
        AaProgramBinding.major_id == major_id,
        AaProgramBinding.grade_year == "2026",
        AaProgramBinding.class_id.is_(None),
        AaProgramBinding.is_deleted.is_(False),
    )).all()
    db.close()

    assert program is not None and program.status == "ENABLED"
    assert len(bindings) == 1
    assert bindings[0].program_id == program_id
    assert bindings[0].status == "ACTIVE"


def test_binding_writer_reuses_frozen_preflight_plan_and_post_confirm_owners():
    import ast
    import inspect
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_confirm_service as service

    source = inspect.getsource(service)
    assert "run_program_import_preflight" in source
    assert "build_program_binding_write_plan" in source
    assert "reconcile_program_confirm_reread" in source
    tree = ast.parse(source)
    assert not any(
        (isinstance(node, ast.Name) and node.id == "bind_grade")
        or (isinstance(node, ast.Attribute) and node.attr == "bind_grade")
        for node in ast.walk(tree)
    )
    assert "data_exchange_confirm_service" not in source
    assert "academic_file_exchange_service" not in source
