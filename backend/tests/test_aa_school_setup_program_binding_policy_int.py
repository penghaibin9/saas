"""INT ordinary Program binding-phase separation contracts."""
from __future__ import annotations

import inspect

import pytest


def _adapter():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter
    return adapter


def _policy():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_policy as policy
    return policy


def _binding_rows():
    return _adapter().normalize_program_import_rows({
        "BINDING": [
            {
                "programSeriesKey": "CS-SOFT", "programVersion": 2,
                "majorId": 10, "gradeYear": "2026",
                "bindingScope": "MAJOR_GRADE",
            },
            {
                "programSeriesKey": "CS-SOFT", "programVersion": 2,
                "majorId": 10, "gradeYear": "2026",
                "bindingScope": "CLASS", "classId": 77,
            },
        ],
    })


def _reconciled_reuse():
    return [{
        "programKey": "SERIES:CS-SOFT:v2",
        "action": "REUSE",
        "programId": "9002",
        "requiresDefinitionReconciliation": False,
        "definitionReconciled": True,
    }]


def test_binding_policy_is_pure_and_has_no_program_or_binding_writer():
    source = inspect.getsource(_policy())
    for forbidden in (
        "get_sessionmaker", "session()", "db.query", "db.execute", "select(",
        "db.add", "db.commit", "db.flush", "with_for_update",
    ):
        assert forbidden not in source


def test_definition_phase_never_writes_binding_even_when_workbook_contains_binding_rows():
    result = _policy().classify_program_binding_phase(
        _binding_rows(),
        [{
            "programKey": "SERIES:CS-SOFT:v2",
            "action": "CREATE",
            "programId": "",
            "createStatus": "DRAFT",
            "predecessorProgramId": "9001",
            "requiresDefinitionReconciliation": False,
        }],
        phase="DEFINITION",
    )
    assert result["bindingWriteAllowed"] is False
    assert result["deferredCount"] == 2
    assert {item["decision"] for item in result["intents"]} == {"DEFER_UNTIL_PUBLISHED"}
    assert {item["scopeKey"] for item in result["intents"]} == {
        "MAJOR:10:GRADE:2026:MAJOR_GRADE",
        "MAJOR:10:GRADE:2026:CLASS:77",
    }


def test_binding_phase_requires_existing_definition_reconciled_program():
    result = _policy().classify_program_binding_phase(
        _binding_rows(),
        [{
            "programKey": "SERIES:CS-SOFT:v2",
            "action": "CREATE",
            "programId": "",
            "createStatus": "DRAFT",
            "requiresDefinitionReconciliation": False,
        }],
        phase="BINDING",
        program_status_by_id={},
    )
    assert result["bindingWriteAllowed"] is False
    assert {item["businessCode"] for item in result["errors"]} == {
        "PROGRAM_BINDING_REQUIRES_EXISTING_RECONCILED_PROGRAM",
    }


def test_binding_phase_requires_published_or_enabled_target():
    result = _policy().classify_program_binding_phase(
        _binding_rows(),
        _reconciled_reuse(),
        phase="BINDING",
        program_status_by_id={"9002": "DRAFT"},
    )
    assert result["bindingWriteAllowed"] is False
    assert {item["businessCode"] for item in result["errors"]} == {
        "PROGRAM_BINDING_TARGET_NOT_PUBLISHED",
    }


def test_binding_phase_reuses_exact_active_scope_and_plans_explicit_supersede_for_other_target():
    result = _policy().classify_program_binding_phase(
        _binding_rows(),
        _reconciled_reuse(),
        phase="BINDING",
        program_status_by_id={"9002": "ENABLED"},
        active_binding_snapshots=[
            {
                "programId": "9002", "majorId": 10, "gradeYear": "2026",
                "bindingScope": "MAJOR_GRADE", "classId": None, "status": "ACTIVE",
            },
            {
                "programId": "8001", "majorId": 10, "gradeYear": "2026",
                "bindingScope": "CLASS", "classId": 77, "status": "ACTIVE",
            },
        ],
    )
    assert result["bindingWriteAllowed"] is True
    by_scope = {item["scopeKey"]: item for item in result["intents"]}
    major = by_scope["MAJOR:10:GRADE:2026:MAJOR_GRADE"]
    clazz = by_scope["MAJOR:10:GRADE:2026:CLASS:77"]
    assert major["action"] == "REUSE"
    assert major["supersedeProgramId"] == ""
    assert clazz["action"] == "CREATE"
    assert clazz["supersedeProgramId"] == "8001"


def test_duplicate_active_binding_scope_fails_closed_before_writer():
    with pytest.raises(ValueError, match="multiple ACTIVE"):
        _policy().classify_program_binding_phase(
            _binding_rows(),
            _reconciled_reuse(),
            phase="BINDING",
            program_status_by_id={"9002": "PUBLISHED"},
            active_binding_snapshots=[
                {
                    "programId": "8001", "majorId": 10, "gradeYear": "2026",
                    "bindingScope": "CLASS", "classId": 77, "status": "ACTIVE",
                },
                {
                    "programId": "8002", "majorId": 10, "gradeYear": "2026",
                    "bindingScope": "CLASS", "classId": 77, "status": "ACTIVE",
                },
            ],
        )


def test_privileged_migration_phase_is_not_smuggled_into_ordinary_import():
    with pytest.raises(ValueError, match="privileged historical migration"):
        _policy().classify_program_binding_phase(
            _binding_rows(),
            _reconciled_reuse(),
            phase="MIGRATION",
            program_status_by_id={"9002": "ENABLED"},
        )
