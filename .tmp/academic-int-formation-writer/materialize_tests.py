from pathlib import Path

path = Path("backend/tests/test_academic_int_ac4_formation_writer_mysql.py")
if path.exists():
    raise SystemExit(f"refuse overwrite existing {path}")
path.write_text(r'''from __future__ import annotations

from types import SimpleNamespace
import inspect
import uuid

import pytest

from app.core.exceptions import AppException

TID = 1000000000000000001


def _seed_program(*, total_credits=3):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram

    db = get_sessionmaker()()
    p = AaProgram(
        tenant_id=TID,
        program_name=f"INT编班写入-{uuid.uuid4().hex[:8]}",
        version=1,
        status="DRAFT",
        total_credits=total_credits,
    )
    db.add(p)
    db.commit()
    pid = int(p.id)
    db.close()
    return pid


@pytest.mark.usefixtures("db_mode")
def test_program_course_create_persists_explicit_direct_formation(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core

    monkeypatch.setattr(core, "_tid", lambda: TID)
    pid = _seed_program()
    body = SimpleNamespace(
        courseId=None,
        courseName="数据库原理",
        openTermNo=1,
        module="专业必修",
        credit=3,
        formationMode="selectable",
    )
    result = core.add_course(pid, {}, body)
    assert result["formationMode"] == "SELECTABLE"

    db = get_sessionmaker()()
    row = db.query(AaProgramCourse).filter(
        AaProgramCourse.id == int(result["programCourseId"]),
        AaProgramCourse.tenant_id == TID,
    ).one()
    assert row.formation_mode == "SELECTABLE"
    db.close()


@pytest.mark.usefixtures("db_mode")
def test_generic_program_course_write_rejects_missing_and_special_modes(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core

    monkeypatch.setattr(core, "_tid", lambda: TID)
    pid = _seed_program()
    for mode, code in ((None, "FORMATION_MODE_REQUIRED"), ("MERGED", "FORMATION_MODE_NOT_DIRECT"),
                       ("RETAKE", "FORMATION_MODE_NOT_DIRECT"), ("LAYERED", "FORMATION_MODE_NOT_DIRECT")):
        body = SimpleNamespace(
            courseId=None, courseName="高等数学", openTermNo=1,
            module="公共基础", credit=3, formationMode=mode,
        )
        with pytest.raises(AppException) as exc:
            core.add_course(pid, {}, body)
        assert exc.value.code == code
        assert exc.value.http_status == 409


@pytest.mark.usefixtures("db_mode")
def test_program_course_update_preserves_when_omitted_and_changes_when_explicit(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core

    monkeypatch.setattr(core, "_tid", lambda: TID)
    pid = _seed_program()
    created = core.add_course(pid, {}, SimpleNamespace(
        courseId=None, courseName="Java程序设计", openTermNo=1,
        module="专业必修", credit=3, formationMode="SELECTABLE",
    ))
    cid = int(created["programCourseId"])

    omitted = SimpleNamespace(
        courseName="Java程序设计A", openTermNo=None, module=None, credit=None,
        formationMode=None, model_fields_set={"courseName"},
    )
    unchanged = core.update_course(cid, {}, omitted)
    assert unchanged["formationMode"] == "SELECTABLE"

    explicit = SimpleNamespace(
        courseName=None, openTermNo=None, module=None, credit=None,
        formationMode="ADMIN_FIXED", model_fields_set={"formationMode"},
    )
    changed = core.update_course(cid, {}, explicit)
    assert changed["formationMode"] == "ADMIN_FIXED"

    db = get_sessionmaker()()
    row = db.query(AaProgramCourse).filter(AaProgramCourse.id == cid, AaProgramCourse.tenant_id == TID).one()
    assert row.formation_mode == "ADMIN_FIXED"
    db.close()


@pytest.mark.usefixtures("db_mode")
def test_legacy_null_formation_blocks_submit_without_state_mutation(monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramCourse
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_program_service as service

    pid = _seed_program(total_credits=3)
    db = get_sessionmaker()()
    db.add(AaProgramCourse(
        tenant_id=TID, program_id=pid, course_name="历史课程",
        open_term_no=1, module="专业必修", credit_snapshot=3,
        formation_mode=None,
    ))
    db.commit()
    db.close()

    monkeypatch.setattr(service, "_tid", lambda: TID)
    monkeypatch.setattr(core, "_tid", lambda: TID)
    monkeypatch.setattr(service.governance, "_ensure_program_scope", lambda *_args, **_kwargs: None)

    with pytest.raises(AppException) as exc:
        service.submit_program(pid, {})
    assert exc.value.code == "PROGRAM_FORMATION_BLOCKED"
    assert exc.value.http_status == 409

    db = get_sessionmaker()()
    program = db.query(AaProgram).filter(AaProgram.id == pid, AaProgram.tenant_id == TID).one()
    assert program.status == "DRAFT"
    db.close()


def test_task_generator_persists_program_course_formation_after_term_match():
    from app.modules.academic_affairs.services import academic_affairs_task_generation_service as generation

    source = inspect.getsource(generation.generate_batch_tx)
    assert "formation_mode = formation_policy.normalize_direct_mode(program_course.formation_mode)" in source
    assert "formation_mode=formation_mode" in source
    term_gate = source.index("if open_term_no != current_semester:")
    formation_gate = source.index("formation_mode = formation_policy.normalize_direct_mode")
    task_write = source.index("formation_mode=formation_mode")
    assert term_gate < formation_gate < task_write


def test_direct_policy_has_exactly_two_generic_modes():
    from app.modules.academic_affairs.services import academic_affairs_program_course_formation_policy as policy

    assert policy.DIRECT_FORMATION_MODES == frozenset({"ADMIN_FIXED", "SELECTABLE"})
    assert policy.SPECIAL_FORMATION_MODES == frozenset({"MERGED", "RETAKE", "LAYERED"})
''')
