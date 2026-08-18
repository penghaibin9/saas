"""INT Program binding source-scope conflicts must stop before DB loaders."""
from __future__ import annotations


def _program_rows(series: str, *, base_row: int) -> list[dict]:
    program_key = f"SERIES:{series}:v1"
    return [
        {
            "rowNo": base_row,
            "logicalGroup": "MAIN",
            "programKey": program_key,
            "definitionKey": program_key,
            "payload": {
                "programSeriesKey": series,
                "programVersion": 1,
                "programName": f"方案-{series}",
                "majorId": 10,
                "gradeYear": "2026",
                "totalCredits": "3",
                "educationYearsAssertion": 3,
            },
        },
        {
            "rowNo": base_row + 1,
            "logicalGroup": "COURSE",
            "programKey": program_key,
            "definitionKey": f"{program_key}|COURSE|CS101@v1",
            "payload": {
                "programKey": program_key,
                "courseKey": "CS101@v1",
                "module": "专业核心",
                "formationMode": "ADMIN_FIXED",
                "openTermNo": 1,
                "creditSnapshot": None,
            },
        },
        {
            "rowNo": base_row + 2,
            "logicalGroup": "CREDIT_REQUIREMENT",
            "programKey": program_key,
            "definitionKey": f"{program_key}|CREDIT|专业核心",
            "payload": {
                "programKey": program_key,
                "module": "专业核心",
                "creditTarget": "3",
            },
        },
        {
            "rowNo": base_row + 3,
            "logicalGroup": "GRADUATION",
            "programKey": program_key,
            "definitionKey": f"{program_key}|GRADUATION|ABILITY|完成培养要求",
            "payload": {
                "programKey": program_key,
                "category": "ABILITY",
                "content": "完成培养要求",
                "sortOrder": 0,
            },
        },
        {
            "rowNo": base_row + 4,
            "logicalGroup": "BINDING",
            "programKey": program_key,
            "definitionKey": f"{program_key}|MAJOR:10:GRADE:2026:CLASS:77",
            "payload": {
                "programKey": program_key,
                "majorId": 10,
                "gradeYear": "2026",
                "bindingScope": "CLASS",
                "classId": 77,
            },
        },
    ]


def _conflicting_rows() -> list[dict]:
    return _program_rows("CS-GENERAL", base_row=2) + _program_rows("CS-OVERRIDE", base_row=20)


def test_source_preflight_rejects_cross_program_same_binding_scope():
    from app.modules.academic_affairs.services.academic_affairs_school_setup_program_import_preflight import (
        program_import_source_preflight,
    )

    result = program_import_source_preflight(_conflicting_rows())

    assert result["sourcePreflightSafe"] is False
    conflicts = [
        item for item in result["errors"]
        if item["businessCode"] == "PROGRAM_BINDING_SOURCE_SCOPE_CONFLICT"
    ]
    assert len(conflicts) == 1
    assert conflicts[0]["evidence"]["scopeKey"] == "MAJOR:10:GRADE:2026:CLASS:77"
    assert conflicts[0]["evidence"]["programKeys"] == [
        "SERIES:CS-GENERAL:v1",
        "SERIES:CS-OVERRIDE:v1",
    ]


def test_pipeline_same_scope_conflict_performs_zero_snapshot_loader_calls():
    from app.modules.academic_affairs.services.academic_affairs_school_setup_program_preflight_pipeline import (
        run_program_import_preflight,
    )

    calls: list[str] = []

    def forbidden(name):
        def _loader(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"{name} must not run for a source-only binding scope conflict")
        return _loader

    result = run_program_import_preflight(
        _conflicting_rows(),
        phase="BINDING",
        load_allowed_major_ids=forbidden("scope"),
        load_major_snapshots=forbidden("major"),
        load_class_snapshots=forbidden("class"),
        load_course_snapshots=forbidden("course"),
        load_program_snapshots=forbidden("program"),
        load_existing_definition_rows=forbidden("definition"),
        load_program_status_by_id=forbidden("status"),
        load_active_binding_snapshots=forbidden("binding"),
    )

    assert calls == []
    assert result["stage"] == "SOURCE"
    assert result["programPreflightSafe"] is False
    assert {item["businessCode"] for item in result["errors"]} == {
        "PROGRAM_BINDING_SOURCE_SCOPE_CONFLICT"
    }
