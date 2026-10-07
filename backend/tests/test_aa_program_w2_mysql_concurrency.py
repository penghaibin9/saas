"""A-W2 Program Authority MySQL concurrency contracts.

Only the scopes that require row-level serialization live here:
- same major+grade binding scope must end with one ACTIVE binding;
- same class override scope must end with one ACTIVE binding;
- one source program version must produce at most one direct successor.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest
from sqlalchemy import select
from tests.support_academic_review_identity import ensure_program_writer_identity, program_writer_context

TID = 1000000000000000001


def _seed_programs_for_binding():
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, College, Major

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    college = College(tenant_id=TID, college_name=f"并发学院-{suffix}", code=f"AW2-{suffix}", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(
        tenant_id=TID,
        college_id=college.id,
        major_name=f"A-W2并发专业-{suffix}",
        code=f"AW2C-{suffix}",
        status="ACTIVE",
        enroll_status="ENROLLING",
    )
    db.add(major)
    db.flush()
    first = AaProgram(
        tenant_id=TID,
        program_name=f"A-W2并发方案A-{suffix}",
        major_id=major.id,
        grade_year="2026",
        version=1,
        status="PUBLISHED",
    )
    second = AaProgram(
        tenant_id=TID,
        program_name=f"A-W2并发方案B-{suffix}",
        major_id=major.id,
        grade_year="2026",
        version=1,
        status="PUBLISHED",
    )
    db.add_all([first, second])
    db.commit()
    result = major.id, first.id, second.id
    db.close()
    return result


def _seed_program_for_versioning():
    from app.db.session import get_sessionmaker
    from app.models import AaProgram

    major_id, _first_id, _second_id = _seed_programs_for_binding()
    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    program = AaProgram(
        tenant_id=TID,
        series_key=f"AW2-SERIES-{suffix}",
        program_name=f"A-W2并发版本-{suffix}",
        major_id=major_id,
        grade_year="2026",
        version=7,
        status="PUBLISHED",
    )
    db.add(program)
    db.commit()
    program_id = program.id
    db.close()
    return program_id


def _writer_authority():
    from app.modules.academic_affairs.services import academic_affairs_program_authority_service as authority
    return authority, ensure_program_writer_identity()


@pytest.mark.usefixtures("db_mode")
def test_w2_same_binding_scope_serializes_to_one_active(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramBinding

    authority, writer = _writer_authority()
    major_id, first_id, second_id = _seed_programs_for_binding()

    def bind(program_id):
        with program_writer_context(writer):
            return authority.bind_grade(program_id, writer, "2026")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(bind, [first_id, second_id]))

    assert len(results) == 2
    assert {int(row["programId"]) for row in results} == {first_id, second_id}

    db = get_sessionmaker()()
    active = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == TID,
        AaProgramBinding.major_id == major_id,
        AaProgramBinding.grade_year == "2026",
        AaProgramBinding.class_id.is_(None),
        AaProgramBinding.status == "ACTIVE",
        AaProgramBinding.is_deleted.is_(False),
    )).all()
    all_rows = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == TID,
        AaProgramBinding.major_id == major_id,
        AaProgramBinding.grade_year == "2026",
        AaProgramBinding.class_id.is_(None),
        AaProgramBinding.is_deleted.is_(False),
    )).all()
    db.close()

    assert len(active) == 1, "same major+grade scope must never expose two ACTIVE bindings"
    assert len(all_rows) == 2
    assert sorted(row.status for row in all_rows) == ["ACTIVE", "SUPERSEDED"]


@pytest.mark.usefixtures("db_mode")
def test_w2_same_class_override_scope_serializes_to_one_active(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramBinding, SchoolClass

    authority, writer = _writer_authority()
    major_id, first_id, second_id = _seed_programs_for_binding()

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    clazz = SchoolClass(
        tenant_id=TID,
        major_id=major_id,
        class_name=f"A-W2并发班级-{suffix}",
        grade="2026",
        status="ACTIVE",
        class_status="NORMAL",
    )
    db.add(clazz)
    db.commit()
    class_id = clazz.id
    db.close()

    def bind(program_id):
        with program_writer_context(writer):
            return authority.bind_grade(program_id, writer, "2026", class_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(bind, [first_id, second_id]))

    assert len(results) == 2
    assert {int(row["programId"]) for row in results} == {first_id, second_id}

    db = get_sessionmaker()()
    active = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == TID,
        AaProgramBinding.major_id == major_id,
        AaProgramBinding.grade_year == "2026",
        AaProgramBinding.class_id == class_id,
        AaProgramBinding.status == "ACTIVE",
        AaProgramBinding.is_deleted.is_(False),
    )).all()
    all_rows = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == TID,
        AaProgramBinding.major_id == major_id,
        AaProgramBinding.grade_year == "2026",
        AaProgramBinding.class_id == class_id,
        AaProgramBinding.is_deleted.is_(False),
    )).all()
    db.close()

    assert len(active) == 1, "same class override scope must never expose two ACTIVE bindings"
    assert len(all_rows) == 2
    assert sorted(row.status for row in all_rows) == ["ACTIVE", "SUPERSEDED"]


@pytest.mark.usefixtures("db_mode")
def test_w2_same_source_version_allows_only_one_direct_successor(monkeypatch):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaProgram

    authority, writer = _writer_authority()
    source_id = _seed_program_for_versioning()

    def create_successor(_):
        try:
            with program_writer_context(writer):
                return ("ok", authority.create_new_version(source_id, writer)["programId"])
        except AppException as exc:
            assert exc.code == "DATA_CONFLICT", exc.message
            return ("conflict", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create_successor, [1, 2]))

    kinds = [kind for kind, _value in results]
    assert kinds.count("ok") == 1
    assert kinds.count("conflict") == 1

    db = get_sessionmaker()()
    successors = db.scalars(select(AaProgram).where(
        AaProgram.tenant_id == TID,
        AaProgram.prev_version_id == source_id,
        AaProgram.is_deleted.is_(False),
    )).all()
    db.close()

    assert len(successors) == 1, "source version row lock must prevent forked v+1 successors"
    assert successors[0].version == 8
