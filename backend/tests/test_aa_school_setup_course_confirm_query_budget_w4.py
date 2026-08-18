"""A-W4 Course confirm bounded-query contract."""
from __future__ import annotations

import json
import re
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import event

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


def _code() -> str:
    digits = int(uuid.uuid4().hex[:8], 16) % 1_000_000
    return f"QB{digits:06d}"


def _row(code: str) -> dict:
    return {
        "courseCode": code,
        "version": "2",
        "courseName": f"课程-{code}-v2",
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


def _seed_enabled_course(code: str) -> None:
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    db = get_sessionmaker()()
    try:
        db.add(AaCourse(
            tenant_id=TID,
            course_code=code,
            course_name=f"历史-{code}",
            course_name_en="Inherited",
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
            description="history",
            applicable_majors_json=json.dumps([]),
            is_all_major=False,
            version=1,
            prev_version_id=None,
            status="ENABLED",
        ))
        db.commit()
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_successor_confirm_queries_course_only_for_locked_preflight_and_final_reread(monkeypatch):
    """Do not re-query predecessors after locked preflight already loaded them."""
    from app.db.session import get_engine

    service = _service(monkeypatch)
    code = _code()
    _seed_enabled_course(code)
    engine = get_engine()
    pattern = re.compile(r"(?<![A-Z0-9_])T_AA_COURSE(?![A-Z0-9_])")
    course_selects = 0

    def before_cursor_execute(_conn, _cursor, statement, *_args, **_kwargs):
        nonlocal course_selects
        upper = statement.strip().upper()
        if upper.startswith("SELECT") and pattern.search(upper):
            course_selects += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        result = service.confirm_course_catalog_import(
            [_row(code)],
            {"currentRoleCode": "ACADEMIC_ADMIN"},
        )
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    assert result["createdCount"] == 1
    assert course_selects == 2, (
        "Course confirm should use one locked preflight SELECT and one final reconciliation SELECT; "
        f"got {course_selects}, indicating a redundant predecessor query"
    )
