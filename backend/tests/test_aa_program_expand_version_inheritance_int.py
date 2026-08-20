"""INT write-side compatibility contract for Program expand columns.

Existing proven series/provenance must survive normal new-version creation. Legacy
NULL evidence must remain unresolved: the version writer may inherit proven facts,
never invent historical identity or formation provenance during the expand phase.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select


TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_program(*, series_key: str | None, formation_mode: str | None) -> int:
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramCourse

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    program = AaProgram(
        tenant_id=TID,
        series_key=series_key,
        program_name=f"INT版本继承-{suffix}",
        major_id=920001,
        grade_year="2026",
        total_credits=3,
        requirement_json='{"creditStructure":[{"module":"MAJOR_CORE","creditTarget":3}]}',
        version=3,
        status="PUBLISHED",
    )
    db.add(program)
    db.flush()
    db.add(AaProgramCourse(
        tenant_id=TID,
        program_id=program.id,
        course_id=930001,
        course_name="INT版本课程",
        open_term_no=2,
        module="MAJOR_CORE",
        credit_snapshot=3,
        formation_mode=formation_mode,
    ))
    db.commit()
    program_id = int(program.id)
    db.close()
    return program_id


def _assert_successor(program_id: int, *, series_key: str | None, formation_mode: str | None) -> None:
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramCourse

    db = get_sessionmaker()()
    successor = db.scalars(select(AaProgram).where(
        AaProgram.tenant_id == TID,
        AaProgram.prev_version_id == int(program_id),
        AaProgram.is_deleted.is_(False),
    )).one()
    courses = db.scalars(select(AaProgramCourse).where(
        AaProgramCourse.tenant_id == TID,
        AaProgramCourse.program_id == successor.id,
        AaProgramCourse.is_deleted.is_(False),
    )).all()
    assert successor.series_key == series_key
    assert successor.version == 4
    assert successor.status == "DRAFT"
    assert len(courses) == 1
    assert courses[0].formation_mode == formation_mode
    db.close()


def _assert_no_successor(program_id: int) -> None:
    from app.db.session import get_sessionmaker
    from app.models import AaProgram

    db = get_sessionmaker()()
    successors = db.scalars(select(AaProgram).where(
        AaProgram.tenant_id == TID,
        AaProgram.prev_version_id == int(program_id),
        AaProgram.is_deleted.is_(False),
    )).all()
    db.close()
    assert successors == [], "unresolved historical series must never be guessed into a successor"


@pytest.mark.usefixtures("db_mode")
def test_new_version_inherits_proven_identity_and_provenance_without_guessing_null_history(client):
    hdr = _hdr(client)

    proven_series = f"INT-SERIES-{uuid.uuid4().hex[:12]}"
    proven_id = _seed_program(
        series_key=proven_series,
        formation_mode="ADMIN_FIXED",
    )
    proven = client.post(f"{BASE}/programs/{proven_id}/new-version", headers=hdr)
    assert proven.status_code == 200, proven.text
    _assert_successor(
        proven_id,
        series_key=proven_series,
        formation_mode="ADMIN_FIXED",
    )

    legacy_id = _seed_program(series_key=None, formation_mode=None)
    legacy = client.post(f"{BASE}/programs/{legacy_id}/new-version", headers=hdr)
    assert legacy.status_code == 409, legacy.text
    payload = legacy.json()
    assert payload["bizCode"] == "PROGRAM_SERIES_UNRESOLVED"
    _assert_no_successor(legacy_id)
