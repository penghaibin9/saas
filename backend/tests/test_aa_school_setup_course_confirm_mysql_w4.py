"""A-W4 Course Catalog confirm transaction / idempotency / MySQL contracts."""
from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

TID = 1000000000000000001


def _service(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_course_service as core
    from app.modules.academic_affairs.services import academic_affairs_school_setup_course_confirm_service as service
    from app.modules.academic_affairs.services import academic_affairs_school_setup_course_preflight_service as bridge

    monkeypatch.setattr(service, "_tid", lambda: TID)
    monkeypatch.setattr(bridge, "_tid", lambda: TID)
    monkeypatch.setattr(core, "_tid", lambda: TID)
    monkeypatch.setattr(
        bridge,
        "build_affairs_context",
        lambda _user, _db: SimpleNamespace(scope_type="TENANT_ALL", college_ids=set()),
    )
    return service


def _code(prefix="WC") -> str:
    digits = int(uuid.uuid4().hex[:8], 16) % 1_000_000
    return f"{prefix}{digits:06d}"


def _row(code: str, *, version=1, name=None, **changes):
    row = {
        "courseCode": code,
        "version": str(version),
        "courseName": name or f"课程-{code}-v{version}",
        "category": "MAJOR_CORE",
        "nature": "REQUIRED",
        "credit": "3",
        "hoursTotal": "48",
        "hoursTheory": "32",
        "hoursPractice": "16",
        "hoursExperiment": "0",
        "hoursComputer": "0",
        "examMode": "EXAM",
        "ownerCollegeId": "",
        "ownerTeacherId": "",
        "isCore": "是",
        "prerequisiteCodes": "",
    }
    row.update(changes)
    return row


def _seed_enabled_course(code: str, *, applicable_json=None):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    db = get_sessionmaker()()
    course = AaCourse(
        tenant_id=TID,
        course_code=code,
        course_name=f"历史-{code}",
        course_name_en="Inherited English Name",
        category="MAJOR_CORE",
        nature="REQUIRED",
        credit=2,
        hours_total=32,
        hours_theory=16,
        hours_practice=16,
        hours_experiment=0,
        hours_computer=0,
        exam_mode="CHECK",
        owner_college_id=None,
        owner_teacher_id=None,
        is_core=False,
        prerequisite_codes_json="[]",
        description="必须由后继版本继承的简介",
        applicable_majors_json=applicable_json if applicable_json is not None else json.dumps([901, 902]),
        is_all_major=False,
        version=1,
        prev_version_id=None,
        status="ENABLED",
    )
    db.add(course)
    db.commit()
    result = int(course.id)
    db.close()
    return result


@pytest.mark.usefixtures("db_mode")
def test_course_confirm_new_v1_is_atomic_and_repeat_confirm_reuses(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    service = _service(monkeypatch)
    code = _code("CI")
    source = [_row(code)]

    first = service.confirm_course_catalog_import(source, {"currentRoleCode": "ACADEMIC_ADMIN"})
    second = service.confirm_course_catalog_import(source, {"currentRoleCode": "ACADEMIC_ADMIN"})

    assert first["confirmedRows"] == 1
    assert first["createdCount"] == 1
    assert first["reusedCount"] == 0
    assert second["confirmedRows"] == 1
    assert second["createdCount"] == 0
    assert second["reusedCount"] == 1
    assert first["reconciliation"][0]["action"] == "CREATE"
    assert second["reconciliation"][0]["action"] == "REUSE"
    assert first["reconciliation"][0]["courseId"] == first["createdCourseIds"][0]
    assert second["reconciliation"][0]["courseId"] == first["createdCourseIds"][0]

    db = get_sessionmaker()()
    rows = db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == TID,
        AaCourse.course_code == code,
        AaCourse.is_deleted.is_(False),
    )).all()
    db.close()
    assert len(rows) == 1
    assert rows[0].version == 1
    assert rows[0].status == "DRAFT"
    assert rows[0].prev_version_id is None


@pytest.mark.usefixtures("db_mode")
def test_course_confirm_successor_inherits_non_template_facts(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    service = _service(monkeypatch)
    code = _code("IH")
    predecessor_id = _seed_enabled_course(code)
    source = [_row(
        code,
        version=2,
        name="导入后的显式中文名",
        category="DISCIPLINE_BASIC",
        nature="ELECTIVE",
        credit="4",
        hoursTotal="64",
        hoursTheory="40",
        hoursPractice="24",
        examMode="EXAM",
        isCore="否",
    )]

    result = service.confirm_course_catalog_import(source, {"currentRoleCode": "ACADEMIC_ADMIN"})
    assert result["createdCount"] == 1
    assert result["reconciliation"][0]["action"] == "CREATE"
    assert result["reconciliation"][0]["courseId"] == result["createdCourseIds"][0]

    db = get_sessionmaker()()
    successor = db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == TID,
        AaCourse.course_code == code,
        AaCourse.version == 2,
        AaCourse.is_deleted.is_(False),
    )).one()
    db.close()

    assert successor.prev_version_id == predecessor_id
    assert successor.status == "DRAFT"
    assert successor.course_name == "导入后的显式中文名"
    assert successor.category == "DISCIPLINE_BASIC"
    assert successor.course_name_en == "Inherited English Name"
    assert successor.description == "必须由后继版本继承的简介"
    assert json.loads(successor.applicable_majors_json) == [901, 902]
    assert successor.is_all_major is False


@pytest.mark.usefixtures("db_mode")
def test_course_confirm_invalid_second_row_writes_nothing(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse
    from app.core.exceptions import AppException

    service = _service(monkeypatch)
    good_code = _code("AT")
    bad_code = _code("BG")
    source = [
        _row(good_code),
        _row(bad_code, version=2),
    ]

    with pytest.raises(AppException) as exc_info:
        service.confirm_course_catalog_import(source, {"currentRoleCode": "ACADEMIC_ADMIN"})
    assert exc_info.value.code == "DATA_CONFLICT"

    db = get_sessionmaker()()
    count = db.scalar(select(func.count()).select_from(AaCourse).where(
        AaCourse.tenant_id == TID,
        AaCourse.course_code.in_([good_code, bad_code]),
        AaCourse.is_deleted.is_(False),
    ))
    db.close()
    assert int(count or 0) == 0


@pytest.mark.usefixtures("db_mode")
def test_course_confirm_corrupt_hidden_predecessor_fails_closed_without_successor(monkeypatch):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    service = _service(monkeypatch)
    code = _code("HD")
    _seed_enabled_course(code, applicable_json="{broken")

    with pytest.raises(AppException) as exc_info:
        service.confirm_course_catalog_import(
            [_row(code, version=2)],
            {"currentRoleCode": "ACADEMIC_ADMIN"},
        )
    assert exc_info.value.code == "DATA_CONFLICT"

    db = get_sessionmaker()()
    count = db.scalar(select(func.count()).select_from(AaCourse).where(
        AaCourse.tenant_id == TID,
        AaCourse.course_code == code,
        AaCourse.version == 2,
        AaCourse.is_deleted.is_(False),
    ))
    db.close()
    assert int(count or 0) == 0


def test_course_confirm_invalid_source_row_is_business_validation_error(monkeypatch):
    from app.core.exceptions import AppException

    service = _service(monkeypatch)
    with pytest.raises(AppException) as exc_info:
        service.confirm_course_catalog_import(
            [_row("bad-code")],
            {"currentRoleCode": "ACADEMIC_ADMIN"},
        )
    assert exc_info.value.code == "VALIDATION_ERROR"


@pytest.mark.usefixtures("db_mode")
def test_course_confirm_concurrent_new_v1_converges_to_one_truth(monkeypatch):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    service = _service(monkeypatch)
    code = _code("CC")
    source = [_row(code)]
    barrier = Barrier(2)

    def confirm(_index: int):
        barrier.wait()
        try:
            result = service.confirm_course_catalog_import(source, {"currentRoleCode": "ACADEMIC_ADMIN"})
            return "ok", result
        except AppException as exc:
            return "conflict", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(confirm, [1, 2]))

    successful = [value for kind, value in results if kind == "ok"]
    conflicts = [value for kind, value in results if kind == "conflict"]
    assert len(successful) in {1, 2}
    assert all(code == "DATA_CONFLICT" for code in conflicts)
    assert sum(int(result["createdCount"]) for result in successful) == 1
    if len(successful) == 2:
        assert sum(int(result["reusedCount"]) for result in successful) == 1

    db = get_sessionmaker()()
    rows = db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == TID,
        AaCourse.course_code == code,
        AaCourse.version == 1,
        AaCourse.is_deleted.is_(False),
    )).all()
    db.close()
    assert len(rows) == 1
