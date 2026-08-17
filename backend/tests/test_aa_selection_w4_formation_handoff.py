"""B-W4 cross-line activation: consume sealed A/INT formation provenance without cloning policy."""
from __future__ import annotations

import importlib.util
import inspect
import uuid
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_selection_course_command_service as command
from app.modules.academic_affairs.services import academic_affairs_selection_formation_dependency as dependency

TID = 1000000000000000001
_RUNTIME = "app.modules.academic_affairs.services.academic_affairs_task_formation_provenance_service"


def _fake_importer(snapshot, *, allowed=True):
    def resolve(_db, task_id, *, tenant_id):
        assert int(task_id) == 31
        assert int(tenant_id) == TID
        return dict(snapshot)

    def importer(name, package=None):
        if name == ".academic_affairs_task_formation_provenance_service":
            return SimpleNamespace(resolve_task_formation_snapshot=resolve)
        if name == ".academic_affairs_task_formation_policy":
            return SimpleNamespace(selection_eligible=lambda mode: bool(allowed and mode == "SELECTABLE"))
        if name == ".academic_affairs_selection_formation_dependency":
            return dependency
        raise AssertionError(f"unexpected import: {name} package={package}")

    return importer


def test_selection_course_writer_calls_cross_line_formation_guard():
    source = inspect.getsource(command.add_course)
    helper = inspect.getsource(command._guard_selection_formation)
    assert "_guard_selection_formation(db, task_id)" in source
    assert "academic_affairs_task_formation_provenance_service" in helper
    assert "academic_affairs_task_formation_policy" in helper
    assert "academic_affairs_selection_formation_dependency" in helper
    assert "selection_eligible" in helper
    assert "FORMATION_SELECTABLE" not in helper
    assert "ADMIN_FIXED" not in helper
    assert "resolve_program_for_scope" not in helper


def test_standalone_b_subseal_only_tolerates_whole_upstream_module_absence(monkeypatch):
    full_name = command._UPSTREAM_PROVENANCE_MODULE

    def missing(name, package=None):
        raise ModuleNotFoundError(f"No module named '{full_name}'", name=full_name)

    monkeypatch.setattr(command.importlib, "import_module", missing)
    assert command._guard_selection_formation(object(), 31) is False


def test_partial_upstream_import_failure_is_not_swallowed(monkeypatch):
    def broken(name, package=None):
        raise ModuleNotFoundError("No module named 'broken_dependency'", name="broken_dependency")

    monkeypatch.setattr(command.importlib, "import_module", broken)
    with pytest.raises(ModuleNotFoundError) as captured:
        command._guard_selection_formation(object(), 31)
    assert captured.value.name == "broken_dependency"


def test_proven_selectable_snapshot_delegates_to_a_policy(monkeypatch):
    snapshot = {
        "status": "PROVEN",
        "sourceProgramCourseId": "17",
        "formationMode": "SELECTABLE",
    }
    monkeypatch.setattr(command._core, "_tid", lambda: TID)
    monkeypatch.setattr(command.importlib, "import_module", _fake_importer(snapshot, allowed=True))
    assert command._guard_selection_formation(object(), 31) is True


def test_proven_non_selectable_snapshot_is_rejected_by_a_policy(monkeypatch):
    snapshot = {
        "status": "PROVEN",
        "sourceProgramCourseId": "17",
        "formationMode": "ADMIN_FIXED",
    }
    monkeypatch.setattr(command._core, "_tid", lambda: TID)
    monkeypatch.setattr(command.importlib, "import_module", _fake_importer(snapshot, allowed=False))
    with pytest.raises(AppException) as captured:
        command._guard_selection_formation(object(), 31)
    assert captured.value.code == "DATA_CONFLICT"
    assert "SELECTION_FORMATION_NOT_SELECTABLE" in str(captured.value.details)


def test_incomplete_snapshot_keeps_existing_b_fail_closed_contract(monkeypatch):
    snapshot = {
        "status": "UNKNOWN",
        "sourceProgramCourseId": "",
        "formationMode": "SELECTABLE",
    }
    monkeypatch.setattr(command._core, "_tid", lambda: TID)
    monkeypatch.setattr(command.importlib, "import_module", _fake_importer(snapshot, allowed=True))
    with pytest.raises(AppException) as captured:
        command._guard_selection_formation(object(), 31)
    assert dependency.BLOCKER_FORMATION_PROVENANCE_UNAVAILABLE in str(captured.value.details)


def _live_runtime_present() -> bool:
    return importlib.util.find_spec(_RUNTIME) is not None


def _live_rows(db, *, source_mode="SELECTABLE", task_mode="SELECTABLE", direct_source=True):
    from app.models import AaProgramCourse, AaTeachingTask

    source = AaProgramCourse(
        tenant_id=TID,
        program_id=880001,
        course_id=770001,
        course_name=f"B-W4-HANDOFF-{uuid.uuid4().hex[:6]}",
        open_term_no=1,
        module="MAJOR_CORE",
        credit_snapshot=2,
        formation_mode=source_mode,
    )
    db.add(source)
    db.flush()
    task = AaTeachingTask(
        tenant_id=TID,
        batch_id=990001,
        course_id=770001,
        course_code="BW4H001",
        course_name="B W4 formation handoff",
        source_program_course_id=source.id if direct_source else None,
        formation_mode=task_mode,
        status="READY",
    )
    db.add(task)
    db.commit()
    return int(source.id), int(task.id)


@pytest.mark.usefixtures("db_mode")
def test_live_int_selectable_provenance_is_accepted(monkeypatch):
    if not _live_runtime_present():
        assert importlib.util.find_spec(_RUNTIME) is None
        return

    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        source_id, task_id = _live_rows(db)
        monkeypatch.setattr(command._core, "_tid", lambda: TID)
        assert command._guard_selection_formation(db, task_id) is True
        assert source_id > 0
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_live_int_non_selectable_provenance_is_blocked(monkeypatch):
    if not _live_runtime_present():
        assert importlib.util.find_spec(_RUNTIME) is None
        return

    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        _source_id, task_id = _live_rows(db, source_mode="ADMIN_FIXED", task_mode="ADMIN_FIXED")
        monkeypatch.setattr(command._core, "_tid", lambda: TID)
        with pytest.raises(AppException) as captured:
            command._guard_selection_formation(db, task_id)
        assert "SELECTION_FORMATION_NOT_SELECTABLE" in str(captured.value.details)
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_live_int_missing_direct_provenance_is_fail_closed(monkeypatch):
    if not _live_runtime_present():
        assert importlib.util.find_spec(_RUNTIME) is None
        return

    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        _source_id, task_id = _live_rows(db, direct_source=False)
        monkeypatch.setattr(command._core, "_tid", lambda: TID)
        with pytest.raises(AppException) as captured:
            command._guard_selection_formation(db, task_id)
        assert dependency.BLOCKER_FORMATION_PROVENANCE_UNAVAILABLE in str(captured.value.details)
    finally:
        db.close()
