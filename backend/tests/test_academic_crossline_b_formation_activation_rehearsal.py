"""Cross-line activation rehearsal: frozen B consumes formal INT formation provenance."""
from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import AppException

TID = 1000000000000000001


def _persist_task(*, source_mode="SELECTABLE", task_mode="SELECTABLE", include_source=True):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse, AaTeachingTask

    db = get_sessionmaker()()
    source_id = None
    if include_source:
        source = AaProgramCourse(
            tenant_id=TID,
            program_id=880001,
            course_id=770001,
            course_name=f"跨线验收-{uuid.uuid4().hex[:8]}",
            open_term_no=1,
            module="MAJOR_CORE",
            credit_snapshot=2,
            formation_mode=source_mode,
        )
        db.add(source)
        db.flush()
        source_id = int(source.id)

    task = AaTeachingTask(
        tenant_id=TID,
        batch_id=990001,
        course_id=770001,
        course_code="XLINE101",
        course_name="跨线 Formation 验收",
        class_id=660001,
        source_program_course_id=source_id,
        formation_mode=task_mode,
        status="PENDING_ASSIGN",
    )
    db.add(task)
    db.commit()
    task_id = int(task.id)
    db.close()
    return source_id, task_id


def _a_snapshot(monkeypatch, task_id: int) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as provenance

    monkeypatch.setattr(provenance, "_tid", lambda: TID)
    return provenance.get_task_formation_snapshot(task_id)


def _b_accept(snapshot: dict, task_id: int) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_selection_formation_dependency as dependency

    return dependency.require_proven_task_formation_snapshot(
        snapshot,
        teaching_task_id=task_id,
    )


@pytest.mark.usefixtures("db_mode")
def test_formal_int_proven_snapshot_flows_directly_into_frozen_b_consumer(monkeypatch):
    source_id, task_id = _persist_task(source_mode="SELECTABLE", task_mode="SELECTABLE")

    snapshot = _a_snapshot(monkeypatch, task_id)
    assert snapshot == {
        "status": "PROVEN",
        "teachingTaskId": str(task_id),
        "sourceProgramCourseId": str(source_id),
        "formationMode": "SELECTABLE",
        "blockers": [],
    }

    accepted = _b_accept(snapshot, task_id)
    assert accepted == {
        "status": "PROVEN",
        "sourceProgramCourseId": str(source_id),
        "formationMode": "SELECTABLE",
    }


@pytest.mark.usefixtures("db_mode")
def test_formal_int_unknown_stays_blocked_in_frozen_b_even_with_weak_runtime_facts(monkeypatch):
    _source_id, task_id = _persist_task(
        task_mode="SELECTABLE",
        include_source=False,
    )

    snapshot = _a_snapshot(monkeypatch, task_id)
    assert snapshot["status"] == "UNKNOWN"
    assert snapshot["sourceProgramCourseId"] == ""
    assert snapshot["formationMode"] == "SELECTABLE"
    assert snapshot["blockers"] == ["SOURCE_PROGRAM_COURSE_ID_MISSING"]

    from app.modules.academic_affairs.services import academic_affairs_selection_formation_dependency as dependency

    with pytest.raises(AppException) as captured:
        _b_accept(snapshot, task_id)
    exc = captured.value
    assert exc.code == "DATA_CONFLICT"
    assert exc.http_status == 409
    assert exc.details["blocker"] == dependency.BLOCKER_FORMATION_PROVENANCE_UNAVAILABLE
    assert exc.details["requiredEvidence"] == [
        "status=PROVEN",
        "sourceProgramCourseId",
        "formationMode",
    ]


@pytest.mark.usefixtures("db_mode")
def test_formal_int_conflict_is_rejected_by_frozen_b_without_policy_duplication(monkeypatch):
    source_id, task_id = _persist_task(
        source_mode="SELECTABLE",
        task_mode="ADMIN_FIXED",
    )

    snapshot = _a_snapshot(monkeypatch, task_id)
    assert snapshot["status"] == "CONFLICT"
    assert snapshot["sourceProgramCourseId"] == str(source_id)
    assert snapshot["formationMode"] == "ADMIN_FIXED"
    assert snapshot["blockers"] == ["TASK_SOURCE_FORMATION_MISMATCH"]

    with pytest.raises(AppException) as captured:
        _b_accept(snapshot, task_id)
    assert captured.value.code == "DATA_CONFLICT"
