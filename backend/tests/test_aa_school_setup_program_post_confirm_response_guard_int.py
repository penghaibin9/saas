"""INT negative contracts for Program post-confirm reread scope guards."""
from __future__ import annotations

import pytest


def _guard():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_post_confirm_response_guard as guard
    return guard


def _definition_preflight():
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "actions": [{
            "programKey": "SERIES:SER-A:v1",
            "action": "CREATE",
            "programId": "",
        }],
        "binding": {"phase": "DEFINITION"},
    }


def _binding_preflight():
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "actions": [{
            "programKey": "SERIES:SER-A:v1",
            "action": "REUSE",
            "programId": "501",
        }],
        "binding": {
            "phase": "BINDING",
            "bindingWriteAllowed": True,
            "errors": [],
            "intents": [{
                "programKey": "SERIES:SER-A:v1",
                "programId": "501",
                "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
                "action": "CREATE",
                "supersedeProgramId": "400",
            }],
        },
    }


def test_definition_program_reread_allows_only_exact_stable_keys():
    guard = _guard()
    rows = [{
        "programId": "501",
        "seriesKey": "SER-A",
        "version": 1,
    }]
    assert guard.guard_definition_program_reread(_definition_preflight(), rows) == rows
    assert guard.target_program_ids_from_reread(_definition_preflight(), rows) == ("501",)

    with pytest.raises(RuntimeError, match="PROGRAM_REREAD_SCOPE_VIOLATION:PROGRAM"):
        guard.guard_definition_program_reread(_definition_preflight(), [
            *rows,
            {"programId": "999", "seriesKey": "SER-B", "version": 1},
        ])


def test_definition_program_reread_rejects_duplicate_stable_key_or_program_id():
    guard = _guard()
    with pytest.raises(RuntimeError, match="PROGRAM_DUPLICATE"):
        guard.guard_definition_program_reread(_definition_preflight(), [
            {"programId": "501", "seriesKey": "SER-A", "version": 1},
            {"programId": "502", "seriesKey": "SER-A", "version": 1},
        ])

    preflight = {
        "stage": "READY",
        "programPreflightSafe": True,
        "actions": [
            {"programKey": "SERIES:SER-A:v1", "action": "CREATE"},
            {"programKey": "SERIES:SER-B:v1", "action": "CREATE"},
        ],
        "binding": {"phase": "DEFINITION"},
    }
    with pytest.raises(RuntimeError, match="PROGRAM_ID_DUPLICATE:501"):
        guard.target_program_ids_from_reread(preflight, [
            {"programId": "501", "seriesKey": "SER-A", "version": 1},
            {"programId": "501", "seriesKey": "SER-B", "version": 1},
        ])


def test_definition_child_reread_rejects_unrelated_program_rows():
    guard = _guard()
    rows = [{"programId": "501", "logicalGroup": "COURSE", "payload": {}}]
    assert guard.guard_definition_child_reread(rows, target_program_ids=("501",)) == rows
    with pytest.raises(RuntimeError, match="PROGRAM_REREAD_SCOPE_VIOLATION:DEFINITION"):
        guard.guard_definition_child_reread([
            *rows,
            {"programId": "999", "logicalGroup": "COURSE", "payload": {}},
        ], target_program_ids=("501",))


def test_binding_reread_is_limited_to_requested_scope_and_target_or_superseded_programs():
    guard = _guard()
    allowed = [
        {
            "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
            "programId": "400",
            "status": "SUPERSEDED",
        },
        {
            "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
            "programId": "501",
            "status": "ACTIVE",
        },
    ]
    assert guard.guard_binding_reread(_binding_preflight(), allowed) == allowed

    with pytest.raises(RuntimeError, match="BINDING_SCOPE"):
        guard.guard_binding_reread(_binding_preflight(), [
            *allowed,
            {
                "scopeKey": "MAJOR:11:GRADE:2026:MAJOR_GRADE",
                "programId": "501",
                "status": "ACTIVE",
            },
        ])
    with pytest.raises(RuntimeError, match="BINDING_PROGRAM"):
        guard.guard_binding_reread(_binding_preflight(), [
            {
                "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
                "programId": "999",
                "status": "ACTIVE",
            },
        ])


def test_binding_status_reread_rejects_unrelated_status_rows_and_does_not_require_superseded_status():
    guard = _guard()
    assert guard.guard_binding_status_reread(
        _binding_preflight(), {"501": "ENABLED"}
    ) == {"501": "ENABLED"}

    with pytest.raises(RuntimeError, match="PROGRAM_STATUS"):
        guard.guard_binding_status_reread(
            _binding_preflight(), {"501": "ENABLED", "400": "DISABLED"}
        )
    with pytest.raises(RuntimeError, match="PROGRAM_STATUS"):
        guard.guard_binding_status_reread(
            _binding_preflight(), {"501": "ENABLED", "999": "ENABLED"}
        )


def test_guards_are_pure_and_do_not_open_db_or_shared_dispatcher_owner():
    import inspect

    source = inspect.getsource(_guard())
    assert "get_sessionmaker" not in source
    assert "session()" not in source
    assert "db.query" not in source
    assert "db.add" not in source
    assert "db.commit" not in source
    assert "data_exchange_confirm_service" not in source
    assert "data_exchange_confirm_legacy" not in source
