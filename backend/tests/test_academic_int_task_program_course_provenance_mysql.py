"""Focused MySQL truth for direct TeachingTask -> ProgramCourse provenance."""
from __future__ import annotations

import uuid

import pytest

TID = 1000000000000000001
OTHER_TID = 1000000000000000002


def _rows(db, *, source_mode="SELECTABLE", task_mode="SELECTABLE", task_course_id=7001, source_course_id=7001, source_tenant=TID):
    from app.models import AaProgramCourse, AaTeachingTask

    source = AaProgramCourse(
        tenant_id=source_tenant,
        program_id=8001,
        course_id=source_course_id,
        course_name=f"PROV-{uuid.uuid4().hex[:6]}",
        open_term_no=1,
        module="MAJOR_CORE",
        credit_snapshot=2,
        formation_mode=source_mode,
    )
    db.add(source)
    db.flush()
    task = AaTeachingTask(
        tenant_id=TID,
        batch_id=9001,
        course_id=task_course_id,
        course_code="PROV101",
        course_name="来源链测试",
        source_program_course_id=source.id,
        formation_mode=task_mode,
        status="PENDING_ASSIGN",
    )
    db.add(task)
    db.commit()
    return int(source.id), int(task.id)


@pytest.mark.usefixtures("db_mode")
def test_complete_direct_snapshot_is_proven_and_matches_b_contract():
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service

    db = get_sessionmaker()()
    source_id, task_id = _rows(db)
    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)
    assert snapshot == {
        "status": "PROVEN",
        "teachingTaskId": str(task_id),
        "sourceProgramCourseId": str(source_id),
        "formationMode": "SELECTABLE",
        "blockers": [],
    }
    db.close()


@pytest.mark.usefixtures("db_mode")
def test_legacy_task_without_direct_source_stays_unknown_and_is_not_rewritten():
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service

    db = get_sessionmaker()()
    task = AaTeachingTask(
        tenant_id=TID, batch_id=9002, course_id=7002, course_code="LEG101",
        course_name="旧任务", source_program_course_id=None, formation_mode="ADMIN_FIXED",
        status="PENDING_ASSIGN",
    )
    db.add(task)
    db.commit()
    task_id = int(task.id)
    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)
    assert snapshot["status"] == "UNKNOWN"
    assert snapshot["sourceProgramCourseId"] == ""
    assert snapshot["blockers"] == ["SOURCE_PROGRAM_COURSE_ID_MISSING"]
    db.expire_all()
    assert db.get(AaTeachingTask, task_id).source_program_course_id is None
    db.close()


@pytest.mark.usefixtures("db_mode")
def test_direct_source_course_mismatch_is_conflict_not_inference():
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service

    db = get_sessionmaker()()
    source_id, task_id = _rows(db, task_course_id=7101, source_course_id=7102)
    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)
    assert snapshot["status"] == "CONFLICT"
    assert snapshot["sourceProgramCourseId"] == str(source_id)
    assert snapshot["blockers"] == ["SOURCE_PROGRAM_COURSE_COURSE_MISMATCH"]
    db.close()


@pytest.mark.usefixtures("db_mode")
def test_direct_source_formation_mismatch_is_conflict():
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service

    db = get_sessionmaker()()
    _source_id, task_id = _rows(db, source_mode="ADMIN_FIXED", task_mode="SELECTABLE")
    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)
    assert snapshot["status"] == "CONFLICT"
    assert snapshot["blockers"] == ["TASK_SOURCE_FORMATION_MISMATCH"]
    db.close()


@pytest.mark.usefixtures("db_mode")
def test_direct_source_with_unresolved_formation_stays_unknown():
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service

    db = get_sessionmaker()()
    source_id, task_id = _rows(db, source_mode=None, task_mode=None)
    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)
    assert snapshot["status"] == "UNKNOWN"
    assert snapshot["sourceProgramCourseId"] == str(source_id)
    assert snapshot["formationMode"] == ""
    assert snapshot["blockers"] == ["FORMATION_MODE_UNRESOLVED"]
    db.close()


@pytest.mark.usefixtures("db_mode")
def test_cross_tenant_direct_source_is_not_accepted_as_provenance():
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service

    db = get_sessionmaker()()
    source_id, task_id = _rows(db, source_tenant=OTHER_TID)
    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)
    assert snapshot["status"] == "CONFLICT"
    assert snapshot["sourceProgramCourseId"] == str(source_id)
    assert snapshot["blockers"] == ["SOURCE_PROGRAM_COURSE_NOT_FOUND"]
    db.close()
