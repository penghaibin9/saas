"""A-W4 Course confirm TOCTOU rollback contract."""
from __future__ import annotations

import json
import uuid
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
    return service, bridge


def _code(prefix: str) -> str:
    digits = int(uuid.uuid4().hex[:8], 16) % 1_000_000
    return f"{prefix}{digits:06d}"


def _row(code: str, *, version: int = 1) -> dict:
    return {
        "courseCode": code,
        "version": str(version),
        "courseName": f"课程-{code}-v{version}",
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


def _seed_enabled_course(code: str) -> int:
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    db = get_sessionmaker()()
    try:
        course = AaCourse(
            tenant_id=TID,
            course_code=code,
            course_name=f"历史-{code}",
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
            applicable_majors_json=json.dumps([]),
            is_all_major=False,
            version=1,
            prev_version_id=None,
            status="ENABLED",
        )
        db.add(course)
        db.commit()
        return int(course.id)
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_confirm_revalidates_dirty_second_row_and_keeps_whole_file_zero_write(monkeypatch):
    """Preview may age; confirm must revalidate all rows before writing any of them."""
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    service, bridge = _service(monkeypatch)
    first_code = _code("TW")
    second_code = _code("TD")
    predecessor_id = _seed_enabled_course(second_code)
    source = [_row(first_code), _row(second_code, version=2)]
    user = {"currentRoleCode": "ACADEMIC_ADMIN"}

    preview = bridge.course_catalog_dry_run(source, user)
    assert preview["invalidRows"] == 0
    assert preview["createRows"] == 2

    db = get_sessionmaker()()
    try:
        predecessor = db.scalars(select(AaCourse).where(
            AaCourse.tenant_id == TID,
            AaCourse.id == predecessor_id,
            AaCourse.is_deleted.is_(False),
        )).one()
        predecessor.status = "DISABLED"
        db.commit()
    finally:
        db.close()

    with pytest.raises(AppException) as exc_info:
        service.confirm_course_catalog_import(source, user)
    assert exc_info.value.code == "DATA_CONFLICT"

    db = get_sessionmaker()()
    try:
        created_count = db.scalar(select(func.count()).select_from(AaCourse).where(
            AaCourse.tenant_id == TID,
            AaCourse.is_deleted.is_(False),
            (
                ((AaCourse.course_code == first_code) & (AaCourse.version == 1))
                | ((AaCourse.course_code == second_code) & (AaCourse.version == 2))
            ),
        ))
        predecessor_status = db.scalar(select(AaCourse.status).where(
            AaCourse.tenant_id == TID,
            AaCourse.id == predecessor_id,
            AaCourse.is_deleted.is_(False),
        ))
    finally:
        db.close()

    assert int(created_count or 0) == 0
    assert predecessor_status == "DISABLED"
