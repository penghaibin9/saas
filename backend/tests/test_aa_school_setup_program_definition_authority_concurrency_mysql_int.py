"""MySQL concurrency contract for new Program-series tenant authority."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import AppException

TID = 1000000000000000001


def _seed_two_majors_and_course():
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, Major, Tenant

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8].upper()
    tenant = db.get(Tenant, TID)
    if tenant is None:
        tenant = Tenant(
            id=TID,
            tenant_code=f"int-program-{suffix.lower()}",
            school_name=f"INT培养方案并发学校-{suffix}",
            status="ACTIVE",
        )
        db.add(tenant)
        db.flush()
    majors = [
        Major(
            tenant_id=TID,
            college_id=880001,
            major_name=f"INT并发专业{index}-{suffix}",
            code=f"CM{index}{suffix}",
            status="ACTIVE",
            education_years=3,
            enroll_status="ENROLLING",
        )
        for index in (1, 2)
    ]
    course = AaCourse(
        tenant_id=TID,
        course_code=f"CC{suffix}",
        course_name=f"INT并发课程-{suffix}",
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
    db.add_all([*majors, course])
    db.commit()
    result = [int(row.id) for row in majors], str(course.course_code)
    db.close()
    return result


def _normalized(*, major_id: int, course_code: str, series_key: str):
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter

    return adapter.normalize_program_import_rows(
        {
            "MAIN": [{
                "programSeriesKey": series_key,
                "programVersion": 1,
                "programName": "INT并发培养方案",
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
            "PRACTICE": [],
            "GRADUATION": [{
                "programSeriesKey": series_key,
                "programVersion": 1,
                "category": "ABILITY",
                "content": "完成专业综合项目并通过考核",
            }],
            "BINDING": [],
        }
    )


def _patch_authority(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_authority_service as authority
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_confirm_service as writer

    monkeypatch.setattr(authority, "_tid", lambda: TID)
    monkeypatch.setattr(writer, "_tid", lambda: TID)
    monkeypatch.setattr(core, "_tid", lambda: TID)
    monkeypatch.setattr(
        writer,
        "build_affairs_context",
        lambda _user, _db: SimpleNamespace(
            scope_type="TENANT_ALL",
            college_ids=set(),
            class_ids=set(),
        ),
    )
    return authority


@pytest.mark.usefixtures("db_mode")
def test_same_new_series_across_different_majors_serializes_to_one_create(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram

    authority = _patch_authority(monkeypatch)
    major_ids, course_code = _seed_two_majors_and_course()
    series_key = f"INT-CONCURRENT-{uuid.uuid4().hex[:12].upper()}"
    sources = [
        _normalized(major_id=major_id, course_code=course_code, series_key=series_key)
        for major_id in major_ids
    ]
    barrier = Barrier(3)

    def worker(rows):
        barrier.wait()
        try:
            result = authority.confirm_program_definition_import(
                rows,
                user={"currentRoleCode": "ACADEMIC_ADMIN"},
            )
            return ("ok", result["domainMutationWriteCount"])
        except AppException as exc:
            return ("error", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, rows) for rows in sources]
        barrier.wait()
        results = [future.result() for future in futures]

    assert sorted(kind for kind, _value in results) == ["error", "ok"]
    assert next(value for kind, value in results if kind == "ok") == 3
    assert next(value for kind, value in results if kind == "error") == "DATA_CONFLICT"

    db = get_sessionmaker()()
    programs = db.scalars(
        select(AaProgram).where(
            AaProgram.tenant_id == TID,
            AaProgram.series_key == series_key,
            AaProgram.version == 1,
            AaProgram.is_deleted.is_(False),
        )
    ).all()
    db.close()
    assert len(programs) == 1
    assert int(programs[0].major_id) in set(major_ids)


def test_only_v1_requires_school_wide_series_anchor():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_authority_service as authority

    assert authority._requires_tenant_series_lock([{
        "logicalGroup": "MAIN",
        "payload": {"programVersion": 1},
    }]) is True
    assert authority._requires_tenant_series_lock([{
        "logicalGroup": "MAIN",
        "payload": {"programVersion": 2},
    }]) is False
    assert authority._requires_tenant_series_lock([{
        "logicalGroup": "COURSE",
        "payload": {"programVersion": 1},
    }]) is False
