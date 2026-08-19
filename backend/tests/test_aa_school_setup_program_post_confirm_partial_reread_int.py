"""INT partial authoritative-reread contracts for multi-Program confirmation."""
from __future__ import annotations

from decimal import Decimal


def _pipeline():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_post_confirm_pipeline as pipeline
    return pipeline


def _preflight_two_programs():
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "actions": [
            {
                "programKey": "SERIES:SER-A:v1",
                "action": "CREATE",
                "programId": "",
                "predecessorProgramId": "",
            },
            {
                "programKey": "SERIES:SER-B:v1",
                "action": "CREATE",
                "programId": "",
                "predecessorProgramId": "",
            },
        ],
        "binding": {"phase": "DEFINITION"},
    }


def _source_program(series: str, major_id: int, course_code: str):
    key = f"SERIES:{series}:v1"
    return [
        {
            "rowNo": 2,
            "logicalGroup": "MAIN",
            "programKey": key,
            "definitionKey": key,
            "payload": {
                "programSeriesKey": series,
                "programVersion": 1,
                "programName": f"方案{series}",
                "majorId": major_id,
                "gradeYear": "2026",
                "totalCredits": Decimal("3"),
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "COURSE",
            "programKey": key,
            "definitionKey": f"{key}|COURSE|{course_code}@v1",
            "payload": {
                "programKey": key,
                "courseKey": f"{course_code}@v1",
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


def _program(series: str, program_id: str, major_id: int):
    return {
        "programId": program_id,
        "seriesKey": series,
        "version": 1,
        "programName": f"方案{series}",
        "majorId": major_id,
        "gradeYear": "2026",
        "totalCredits": Decimal("3"),
        "prevProgramId": "",
        "status": "DRAFT",
    }


def _definitions(program_id: str, course_code: str):
    return [
        {
            "programId": program_id,
            "logicalGroup": "COURSE",
            "payload": {
                "courseKey": f"{course_code}@v1",
                "formationMode": "ADMIN_FIXED",
                "module": "核心",
                "openTermNo": 1,
                "creditSnapshot": Decimal("3"),
            },
        },
        {
            "programId": program_id,
            "logicalGroup": "CREDIT_REQUIREMENT",
            "payload": {"module": "核心", "creditTarget": Decimal("3")},
        },
        {
            "programId": program_id,
            "logicalGroup": "GRADUATION",
            "payload": {"category": "ABILITY", "content": "目标", "sortOrder": 0},
        },
    ]


def _course_snapshots():
    return [
        {"courseCode": "CS101", "version": 1, "credit": Decimal("3")},
        {"courseCode": "EE101", "version": 1, "credit": Decimal("3")},
    ]


def test_multi_program_partial_main_reread_keeps_good_hash_and_reports_missing_program():
    source = [
        *_source_program("SER-A", 10, "CS101"),
        *_source_program("SER-B", 11, "EE101"),
    ]
    result = _pipeline().reconcile_program_confirm_reread(
        _preflight_two_programs(),
        normalized_rows=source,
        authoritative_program_snapshots=[_program("SER-A", "501", 10)],
        authoritative_definition_rows=_definitions("501", "CS101"),
        course_snapshots=_course_snapshots(),
    )

    assert result["phase"] == "DEFINITION"
    assert result["reconciliationSafe"] is False
    assert result["programCount"] == 2
    assert result["items"] == [{
        "programKey": "SERIES:SER-A:v1",
        "programId": "501",
        "action": "CREATE",
        "definitionHash": result["items"][0]["definitionHash"],
        "rereadDefinitionHash": result["items"][0]["rereadDefinitionHash"],
        "hashMatch": True,
        "relationship": {"prevProgramId": "", "expectedPrevProgramId": ""},
    }]
    assert result["items"][0]["definitionHash"] == result["items"][0]["rereadDefinitionHash"]
    assert [item["businessCode"] for item in result["errors"]] == ["PROGRAM_REREAD_NOT_FOUND"]
    assert result["errors"][0]["programKey"] == "SERIES:SER-B:v1"


def test_existing_program_with_missing_child_group_is_hash_mismatch_not_scope_error():
    source = _source_program("SER-A", 10, "CS101")
    incomplete = [
        row for row in _definitions("501", "CS101")
        if row["logicalGroup"] != "GRADUATION"
    ]
    preflight = {
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
    result = _pipeline().reconcile_program_confirm_reread(
        preflight,
        normalized_rows=source,
        authoritative_program_snapshots=[_program("SER-A", "501", 10)],
        authoritative_definition_rows=incomplete,
        course_snapshots=_course_snapshots(),
    )

    assert result["reconciliationSafe"] is False
    assert result["items"][0]["hashMatch"] is False
    assert [item["businessCode"] for item in result["errors"]] == [
        "PROGRAM_REREAD_DEFINITION_HASH_MISMATCH"
    ]
