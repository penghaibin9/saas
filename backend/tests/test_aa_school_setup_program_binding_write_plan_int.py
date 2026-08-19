"""INT contract for Program BINDING transaction mutation intent."""
from __future__ import annotations

import inspect

import pytest


def _planner():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_write_plan as planner
    return planner


def _preflight(intents):
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "binding": {
            "phase": "BINDING",
            "bindingWriteAllowed": True,
            "errors": [],
            "intents": intents,
        },
    }


def test_exact_active_binding_reuse_is_zero_mutation():
    plan = _planner().build_program_binding_write_plan(_preflight([{
        "row": 2,
        "programKey": "SERIES:SER-A:v2",
        "programId": "9002",
        "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
        "action": "REUSE",
        "supersedeProgramId": "",
    }]))
    assert plan["sharedTransactionRequired"] is True
    assert plan["rerunLockedPreflightRequired"] is True
    assert plan["plans"] == [{
        "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
        "action": "REUSE",
        "programId": "9002",
        "lockOrder": [],
        "mutations": [],
        "writeCount": 0,
    }]


def test_major_grade_create_locks_target_then_shared_major_anchor_then_active_scope():
    plan = _planner().build_program_binding_write_plan(_preflight([{
        "row": 2,
        "programKey": "SERIES:SER-A:v2",
        "programId": "9002",
        "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
        "action": "CREATE",
        "supersedeProgramId": "8001",
    }]))
    item = plan["plans"][0]
    assert item["lockOrder"] == [
        "PROGRAM:9002",
        "MAJOR:10",
        "ACTIVE_BINDING_SCOPE:MAJOR:10:GRADE:2026:MAJOR_GRADE",
    ]
    assert item["mutations"] == [
        {
            "type": "SUPERSEDE_ACTIVE_BINDING",
            "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
            "expectedProgramId": "8001",
            "nextStatus": "SUPERSEDED",
        },
        {
            "type": "INSERT_ACTIVE_BINDING",
            "programId": "9002",
            "majorId": 10,
            "gradeYear": "2026",
            "classId": None,
            "status": "ACTIVE",
        },
        {"type": "SET_TARGET_PROGRAM_STATUS", "programId": "9002", "status": "ENABLED"},
        {
            "type": "APPEND_PROGRAM_AUDIT",
            "programId": "9002",
            "action": "BIND",
            "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
        },
    ]


def test_class_create_uses_class_anchor_not_major_anchor_and_does_not_invent_supersede():
    plan = _planner().build_program_binding_write_plan(_preflight([{
        "row": 3,
        "programKey": "SERIES:SER-A:v2",
        "programId": "9002",
        "scopeKey": "MAJOR:10:GRADE:2026:CLASS:77",
        "action": "CREATE",
        "supersedeProgramId": "",
    }]))
    item = plan["plans"][0]
    assert item["lockOrder"] == [
        "PROGRAM:9002",
        "CLASS:77",
        "ACTIVE_BINDING_SCOPE:MAJOR:10:GRADE:2026:CLASS:77",
    ]
    assert all(mutation["type"] != "SUPERSEDE_ACTIVE_BINDING" for mutation in item["mutations"])
    insert = next(mutation for mutation in item["mutations"] if mutation["type"] == "INSERT_ACTIVE_BINDING")
    assert insert["majorId"] == 10
    assert insert["gradeYear"] == "2026"
    assert insert["classId"] == 77


def test_binding_plan_fails_closed_on_unsafe_phase_duplicate_scope_or_unknown_action():
    with pytest.raises(ValueError, match="green full preflight"):
        _planner().build_program_binding_write_plan({
            "stage": "BINDING", "programPreflightSafe": False, "binding": {},
        })
    with pytest.raises(ValueError, match="BINDING-phase only"):
        _planner().build_program_binding_write_plan({
            "stage": "READY",
            "programPreflightSafe": True,
            "binding": {"phase": "DEFINITION", "bindingWriteAllowed": False, "errors": []},
        })
    duplicate = {
        "programId": "9002",
        "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
        "action": "REUSE",
    }
    with pytest.raises(ValueError, match="duplicate Program binding mutation scope"):
        _planner().build_program_binding_write_plan(_preflight([duplicate, dict(duplicate)]))
    with pytest.raises(ValueError, match="unsupported Program binding mutation action"):
        _planner().build_program_binding_write_plan(_preflight([{
            "programId": "9002",
            "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
            "action": "OVERWRITE",
        }]))


def test_binding_plan_never_calls_interactive_bind_grade_or_opens_its_own_transaction():
    source = inspect.getsource(_planner())
    assert "bind_grade" in source  # docs explicitly explain why it is forbidden
    assert "academic_affairs_program_authority_service" not in source
    assert "get_sessionmaker" not in source
    assert "session()" not in source
    assert "with_for_update" not in source
    assert "db.add" not in source
    assert "db.commit" not in source
