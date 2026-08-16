"""INT Program binding source-scope exclusivity contract."""
from __future__ import annotations


def _adapter():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter
    return adapter


def _policy():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_policy as policy
    return policy


def test_binding_phase_rejects_two_programs_competing_for_same_source_scope():
    rows = _adapter().normalize_program_import_rows({
        "BINDING": [
            {
                "programSeriesKey": "CS-GENERAL",
                "programVersion": 2,
                "majorId": 10,
                "gradeYear": "2026",
                "bindingScope": "CLASS",
                "classId": 77,
            },
            {
                "programSeriesKey": "CS-OVERRIDE",
                "programVersion": 1,
                "majorId": 10,
                "gradeYear": "2026",
                "bindingScope": "CLASS",
                "classId": 77,
            },
        ],
    })
    actions = [
        {
            "programKey": "SERIES:CS-GENERAL:v2",
            "action": "REUSE",
            "programId": "9002",
            "requiresDefinitionReconciliation": False,
            "definitionReconciled": True,
        },
        {
            "programKey": "SERIES:CS-OVERRIDE:v1",
            "action": "REUSE",
            "programId": "9101",
            "requiresDefinitionReconciliation": False,
            "definitionReconciled": True,
        },
    ]

    result = _policy().classify_program_binding_phase(
        rows,
        actions,
        phase="BINDING",
        program_status_by_id={"9002": "ENABLED", "9101": "PUBLISHED"},
        active_binding_snapshots=[],
    )

    assert result["bindingWriteAllowed"] is False
    assert result["intents"] == []
    assert len(result["errors"]) == 1
    error = result["errors"][0]
    assert error["businessCode"] == "PROGRAM_BINDING_SOURCE_SCOPE_CONFLICT"
    assert error["evidence"]["scopeKey"] == "MAJOR:10:GRADE:2026:CLASS:77"
    assert error["evidence"]["programKeys"] == [
        "SERIES:CS-GENERAL:v2",
        "SERIES:CS-OVERRIDE:v1",
    ]
    assert error["evidence"]["rows"] == [2, 3]


def test_definition_phase_remains_write_free_even_with_future_scope_conflict():
    rows = _adapter().normalize_program_import_rows({
        "BINDING": [
            {
                "programSeriesKey": "CS-A",
                "programVersion": 1,
                "majorId": 10,
                "gradeYear": "2026",
                "bindingScope": "MAJOR_GRADE",
            },
            {
                "programSeriesKey": "CS-B",
                "programVersion": 1,
                "majorId": 10,
                "gradeYear": "2026",
                "bindingScope": "MAJOR_GRADE",
            },
        ],
    })

    result = _policy().classify_program_binding_phase(
        rows,
        [],
        phase="DEFINITION",
    )

    assert result["bindingWriteAllowed"] is False
    assert result["deferredCount"] == 2
    assert result["errors"] == []
    assert {item["decision"] for item in result["intents"]} == {"DEFER_UNTIL_PUBLISHED"}
