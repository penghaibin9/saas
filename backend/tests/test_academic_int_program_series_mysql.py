"""Focused MySQL acceptance for INT Program stable-series writer semantics."""
from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

TID = 1000000000000000001


def _patch_tenant(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_program_authority_service as authority
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core

    monkeypatch.setattr(authority, "_tid", lambda: TID)
    monkeypatch.setattr(core, "_tid", lambda: TID)
    return core, authority


@pytest.mark.usefixtures("db_mode")
def test_root_mints_prg_series_and_successor_inherits_locked_source(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramCourse

    core, authority = _patch_tenant(monkeypatch)
    body = SimpleNamespace(
        programName=f"INT稳定系列-{uuid.uuid4().hex[:8]}",
        majorId=None,
        gradeYear="2026",
        totalCredits=3,
        requirement={},
    )
    root_result = core.create_program(body, None)
    root_id = int(root_result["programId"])

    db = get_sessionmaker()()
    root = db.get(AaProgram, root_id)
    assert root.series_key and root.series_key.startswith("PRG-")
    assert len(root.series_key) <= 64
    root_series = root.series_key
    root.status = "PUBLISHED"
    db.add(AaProgramCourse(
        tenant_id=TID,
        program_id=root.id,
        course_id=930001,
        course_name="INT稳定系列课程",
        open_term_no=1,
        module="MAJOR_CORE",
        credit_snapshot=3,
        formation_mode="ADMIN_FIXED",
    ))
    db.commit()
    db.close()

    created = authority.create_new_version(root_id, None)
    successor_id = int(created["programId"])

    db = get_sessionmaker()()
    successor = db.get(AaProgram, successor_id)
    courses = db.scalars(select(AaProgramCourse).where(
        AaProgramCourse.tenant_id == TID,
        AaProgramCourse.program_id == successor_id,
        AaProgramCourse.is_deleted.is_(False),
    )).all()
    assert successor.prev_version_id == root_id
    assert successor.version == 2
    assert successor.series_key == root_series
    assert len(courses) == 1
    assert courses[0].formation_mode == "ADMIN_FIXED"
    db.close()


@pytest.mark.usefixtures("db_mode")
def test_unresolved_legacy_source_fails_closed_without_creating_successor(monkeypatch):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaProgram

    _core, authority = _patch_tenant(monkeypatch)
    db = get_sessionmaker()()
    source = AaProgram(
        tenant_id=TID,
        series_key=None,
        program_name=f"INT旧脏系列-{uuid.uuid4().hex[:8]}",
        major_id=None,
        grade_year="2025",
        version=3,
        status="PUBLISHED",
    )
    db.add(source)
    db.commit()
    source_id = int(source.id)
    db.close()

    with pytest.raises(AppException) as raised:
        authority.create_new_version(source_id, None)
    assert getattr(raised.value, "code", None) == "PROGRAM_SERIES_UNRESOLVED"

    db = get_sessionmaker()()
    successors = db.scalars(select(AaProgram).where(
        AaProgram.tenant_id == TID,
        AaProgram.prev_version_id == source_id,
        AaProgram.is_deleted.is_(False),
    )).all()
    assert successors == []
    db.close()


@pytest.mark.usefixtures("db_mode")
def test_mysql_unique_series_version_rejects_duplicate_non_null_identity(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram

    _patch_tenant(monkeypatch)
    series = f"PRG-TEST-{uuid.uuid4().hex.upper()}"
    db = get_sessionmaker()()
    db.add(AaProgram(
        tenant_id=TID, series_key=series, program_name="INT唯一系列A",
        version=9, status="DRAFT",
    ))
    db.commit()
    db.add(AaProgram(
        tenant_id=TID, series_key=series, program_name="INT唯一系列B",
        version=9, status="DRAFT",
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()
