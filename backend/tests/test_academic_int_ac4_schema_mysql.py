"""INT A-C4 shared schema: real MySQL constraints and no guessed legacy backfill."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, OperationalError

from app.db.session import get_sessionmaker
from app.models import AaProgramCourse, AaTeachingTask, AaTeachingTaskBatch

MODES = {"ADMIN_FIXED", "SELECTABLE", "MERGED", "RETAKE", "LAYERED"}


def _mysql_code(exc: Exception) -> int | None:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    return int(args[0]) if args and isinstance(args[0], int) else None


def _batch(*, tenant_id: int, term_id: int, key: str | None, name: str):
    return AaTeachingTaskBatch(
        tenant_id=tenant_id, term_id=term_id, batch_name=name, college_id=None,
        editable_scope_key=key, status="DRAFT",
    )


def _task(*, tenant_id: int, batch_id: int, course_id: int, mode: str | None):
    return AaTeachingTask(
        tenant_id=tenant_id, batch_id=batch_id, course_id=course_id,
        course_code=f"INT-{course_id}", course_name=f"INT course {course_id}",
        formation_mode=mode, is_merged=mode == "MERGED", no_auto_schedule=False,
        status="READY",
    )


def _program_course(*, tenant_id: int, program_id: int, label: str, mode: str | None):
    return AaProgramCourse(
        tenant_id=tenant_id, program_id=program_id, course_name=label,
        open_term_no=1, formation_mode=mode,
    )


def test_int_ac4_model_and_migration_contract_is_complete_additive_and_non_guessing():
    assert AaProgramCourse.__table__.c.formation_mode.type.length == 20
    assert AaProgramCourse.__table__.c.formation_mode.nullable is True
    assert AaTeachingTaskBatch.__table__.c.editable_scope_key.type.length == 64
    assert AaTeachingTaskBatch.__table__.c.editable_scope_key.nullable is True
    assert AaTeachingTask.__table__.c.formation_mode.type.length == 20
    assert AaTeachingTask.__table__.c.formation_mode.nullable is True

    program_checks = {c.name: str(c.sqltext) for c in AaProgramCourse.__table__.constraints if c.name}
    task_checks = {c.name: str(c.sqltext) for c in AaTeachingTask.__table__.constraints if c.name}
    for name, checks in (("ck_aa_program_course_formation_mode", program_checks), ("ck_aa_teaching_task_formation_mode", task_checks)):
        assert name in checks
        for mode in MODES:
            assert mode in checks[name]

    batch_unique = {c.name: tuple(c.columns.keys()) for c in AaTeachingTaskBatch.__table__.constraints if c.name}
    assert batch_unique["uk_aa_task_batch_editable_scope"] == ("tenant_id", "editable_scope_key")

    source = Path("alembic/versions/20260816_academic_int_ac4_schema.py").read_text(encoding="utf-8")
    upper = source.upper()
    assert 'down_revision = "20260816_internship_e_m8"' in source
    assert "UPDATE T_AA_PROGRAM_COURSE" not in upper
    assert "UPDATE T_AA_TEACHING_TASK" not in upper
    assert "UPDATE T_AA_TEACHING_TASK_BATCH" not in upper
    assert "ADMIN_FIXED" in source and "editable_scope_key" in source


def test_int_ac4_mysql_enforces_scope_unique_and_both_formation_vocabularies(db_mode):
    db = get_sessionmaker()()
    try:
        inspector = inspect(db.bind)
        pc_columns = {c["name"]: c for c in inspector.get_columns("t_aa_program_course")}
        batch_columns = {c["name"]: c for c in inspector.get_columns("t_aa_teaching_task_batch")}
        task_columns = {c["name"]: c for c in inspector.get_columns("t_aa_teaching_task")}
        assert pc_columns["formation_mode"]["type"].length == 20
        assert pc_columns["formation_mode"]["nullable"] is True
        assert batch_columns["editable_scope_key"]["type"].length == 64
        assert batch_columns["editable_scope_key"]["nullable"] is True
        assert task_columns["formation_mode"]["type"].length == 20
        assert task_columns["formation_mode"]["nullable"] is True

        uniques = {u["name"]: tuple(u["column_names"]) for u in inspector.get_unique_constraints("t_aa_teaching_task_batch")}
        assert uniques["uk_aa_task_batch_editable_scope"] == ("tenant_id", "editable_scope_key")
        pc_checks = {c["name"]: c["sqltext"] for c in inspector.get_check_constraints("t_aa_program_course")}
        task_checks = {c["name"]: c["sqltext"] for c in inspector.get_check_constraints("t_aa_teaching_task")}
        assert "ck_aa_program_course_formation_mode" in pc_checks
        assert "ck_aa_teaching_task_formation_mode" in task_checks

        tenant = 1000000000000008811
        key = "V1:TERM:202601:SCHOOL"
        first = _batch(tenant_id=tenant, term_id=202601, key=key, name="INT A-C4 1")
        db.add(first)
        db.commit()
        db.refresh(first)

        db.add(_batch(tenant_id=tenant, term_id=202601, key=key, name="INT A-C4 duplicate"))
        with pytest.raises(IntegrityError) as duplicate:
            db.commit()
        assert _mysql_code(duplicate.value) == 1062
        db.rollback()

        db.add_all([
            _batch(tenant_id=tenant, term_id=202601, key=None, name="INT history 1"),
            _batch(tenant_id=tenant, term_id=202601, key=None, name="INT history 2"),
        ])
        db.commit()

        db.add_all([
            _program_course(tenant_id=tenant, program_id=88001, label="explicit SELECTABLE", mode="SELECTABLE"),
            _program_course(tenant_id=tenant, program_id=88001, label="legacy unknown", mode=None),
            _task(tenant_id=tenant, batch_id=first.id, course_id=99101, mode="SELECTABLE"),
            _task(tenant_id=tenant, batch_id=first.id, course_id=99102, mode=None),
        ])
        db.commit()

        db.add(_program_course(tenant_id=tenant, program_id=88001, label="invalid", mode="ELECTIVE"))
        with pytest.raises(OperationalError) as invalid_program:
            db.commit()
        assert _mysql_code(invalid_program.value) == 3819
        db.rollback()

        db.add(_task(tenant_id=tenant, batch_id=first.id, course_id=99103, mode="ELECTIVE"))
        with pytest.raises(OperationalError) as invalid_task:
            db.commit()
        assert _mysql_code(invalid_task.value) == 3819
        db.rollback()
    finally:
        db.close()
