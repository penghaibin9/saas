"""INT contracts for the guarded Program post-confirm entrypoint."""
from __future__ import annotations

from decimal import Decimal

import pytest


def _pipeline():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_post_confirm_pipeline as pipeline
    return pipeline


def _definition_preflight():
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "actions": [{
            "programKey": "SERIES:SER-A:v1",
            "action": "CREATE",
            "programId": "",
            "predecessorProgramId": "",
        }],
        "binding": {"phase": "DEFINITION"},
    }


def _definition_source():
    key = "SERIES:SER-A:v1"
    return [
        {
            "rowNo": 2,
            "logicalGroup": "MAIN",
            "programKey": key,
            "definitionKey": key,
            "payload": {
                "programSeriesKey": "SER-A",
                "programVersion": 1,
                "programName": "方案A",
                "majorId": 10,
                "gradeYear": "2026",
                "totalCredits": Decimal("3"),
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "COURSE",
            "programKey": key,
            "definitionKey": f"{key}|COURSE|CS101@v1",
            "payload": {
                "programKey": key,
                "courseKey": "CS101@v1",
                "formationMode": "ADMIN_FIXED",
                "module": "核心",
                "openTermNo": 1,
                "creditSnapshot": None,
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "CREDIT_REQUIREMENT",
            "programKey": key,
            "definitionKey": f"{key}|CREDIT|核心",
            "payload": {"programKey": key, "module": "核心", "creditTarget": Decimal("3")},
        },
        {
            "rowNo": 2,
            "logicalGroup": "GRADUATION",
            "programKey": key,
            "definitionKey": f"{key}|GRADUATION|ABILITY|目标",
            "payload": {"programKey": key, "category": "ABILITY", "content": "目标", "sortOrder": 0},
        },
    ]


def _program():
    return {
        "programId": "501",
        "seriesKey": "SER-A",
        "version": 1,
        "programName": "方案A",
        "majorId": 10,
        "gradeYear": "2026",
        "totalCredits": Decimal("3"),
        "prevProgramId": "",
        "status": "DRAFT",
    }


def _definitions():
    return [
        {
            "programId": "501",
            "logicalGroup": "COURSE",
            "payload": {
                "courseKey": "CS101@v1",
                "formationMode": "ADMIN_FIXED",
                "module": "核心",
                "openTermNo": 1,
                "creditSnapshot": Decimal("3"),
            },
        },
        {
            "programId": "501",
            "logicalGroup": "CREDIT_REQUIREMENT",
            "payload": {"module": "核心", "creditTarget": Decimal("3")},
        },
        {
            "programId": "501",
            "logicalGroup": "GRADUATION",
            "payload": {"category": "ABILITY", "content": "目标", "sortOrder": 0},
        },
    ]


def test_definition_entrypoint_guards_then_reconciles_hash():
    result = _pipeline().reconcile_program_confirm_reread(
        _definition_preflight(),
        normalized_rows=_definition_source(),
        authoritative_program_snapshots=[_program()],
        authoritative_definition_rows=_definitions(),
        course_snapshots=[{"courseCode": "CS101", "version": 1, "credit": Decimal("3")}],
    )
    assert result["phase"] == "DEFINITION"
    assert result["reconciliationSafe"] is True
    assert result["items"][0]["hashMatch"] is True


def test_definition_entrypoint_rejects_overfetch_before_semantic_reconciliation():
    with pytest.raises(RuntimeError, match="PROGRAM_REREAD_SCOPE_VIOLATION:PROGRAM"):
        _pipeline().reconcile_program_confirm_reread(
            _definition_preflight(),
            normalized_rows=_definition_source(),
            authoritative_program_snapshots=[
                _program(),
                {
                    "programId": "999",
                    "seriesKey": "SER-B",
                    "version": 1,
                    "programName": "别的方案",
                    "majorId": 11,
                    "gradeYear": "2026",
                    "totalCredits": Decimal("3"),
                    "prevProgramId": "",
                    "status": "DRAFT",
                },
            ],
            authoritative_definition_rows=_definitions(),
            course_snapshots=[{"courseCode": "CS101", "version": 1, "credit": Decimal("3")}],
        )


def _binding_preflight():
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "actions": [{
            "programKey": "SERIES:SER-A:v1",
            "action": "REUSE",
            "programId": "501",
            "definitionReconciled": True,
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


def test_binding_entrypoint_guards_scope_and_reconciles_relationship():
    result = _pipeline().reconcile_program_confirm_reread(
        _binding_preflight(),
        authoritative_binding_snapshots=[
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
        ],
        authoritative_program_status_by_id={"501": "ENABLED"},
    )
    assert result["phase"] == "BINDING"
    assert result["reconciliationSafe"] is True
    assert result["items"][0]["activeRelationshipMatch"] is True
    assert result["items"][0]["supersedeRelationshipMatch"] is True
    assert result["items"][0]["targetStatusMatch"] is True


def test_binding_entrypoint_rejects_unrelated_status_evidence():
    with pytest.raises(RuntimeError, match="PROGRAM_STATUS"):
        _pipeline().reconcile_program_confirm_reread(
            _binding_preflight(),
            authoritative_binding_snapshots=[
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
            ],
            authoritative_program_status_by_id={"501": "ENABLED", "999": "ENABLED"},
        )
