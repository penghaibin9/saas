"""INT predecessor-alias contract for Program post-confirm rereads."""
from __future__ import annotations

import pytest


def _pipeline():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_post_confirm_pipeline as pipeline
    return pipeline


def _normalized_main():
    return [{
        "rowNo": 2,
        "logicalGroup": "MAIN",
        "programKey": "SERIES:CS-SOFT:v2",
        "definitionKey": "SERIES:CS-SOFT:v2",
        "payload": {
            "programSeriesKey": "CS-SOFT",
            "programVersion": 2,
            "programName": "软件技术2026培养方案V2",
            "majorId": 10,
            "gradeYear": "2026",
            "totalCredits": 3,
            "educationYearsAssertion": 3,
        },
    }]


def _preflight():
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "binding": {"phase": "DEFINITION", "bindingWriteAllowed": False},
        "actions": [{
            "programKey": "SERIES:CS-SOFT:v2",
            "action": "CREATE",
            "programId": "",
            "createStatus": "DRAFT",
            "predecessorProgramId": "501",
            "requiresDefinitionReconciliation": False,
        }],
    }


def test_definition_reread_accepts_db_prev_version_alias_without_losing_vn_relationship():
    result = _pipeline().reconcile_program_confirm_reread(
        _preflight(),
        normalized_rows=_normalized_main(),
        authoritative_program_snapshots=[{
            "programId": "777",
            "seriesKey": "CS-SOFT",
            "version": 2,
            "programName": "软件技术2026培养方案V2",
            "majorId": 10,
            "gradeYear": "2026",
            "totalCredits": 3,
            "prevVersionId": "501",
            "status": "DRAFT",
        }],
        authoritative_definition_rows=[],
        course_snapshots=[],
    )

    assert result["reconciliationSafe"] is True
    assert result["importedPrograms"] == 1
    assert result["reusedPrograms"] == 0
    assert result["items"][0]["relationship"] == {
        "prevProgramId": "501",
        "expectedPrevProgramId": "501",
    }


def test_conflicting_predecessor_aliases_fail_closed_before_reconciliation():
    with pytest.raises(RuntimeError, match="PROGRAM_REREAD_PREDECESSOR_ALIAS_CONFLICT"):
        _pipeline()._normalize_program_predecessor_aliases([{
            "programId": "777",
            "prevProgramId": "501",
            "prevVersionId": "999",
        }])


def test_matching_predecessor_aliases_are_canonicalized_deterministically():
    rows = _pipeline()._normalize_program_predecessor_aliases([{
        "programId": "777",
        "prevProgramId": 501,
        "prevVersionId": "501",
    }])
    assert rows == [{
        "programId": "777",
        "prevProgramId": "501",
        "prevVersionId": "501",
    }]
