"""INT pipeline contract for immutable Program-series major/grade scope."""
from __future__ import annotations

import pytest


def _rows(*, major_id: int, grade_year: str):
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter

    return adapter.normalize_program_import_rows(
        {
            "MAIN": [{
                "programSeriesKey": "CS-SOFT",
                "programVersion": 2,
                "programName": "软件技术培养方案V2",
                "majorId": major_id,
                "gradeYear": grade_year,
                "totalCredits": "3",
                "educationYears": 3,
            }],
            "COURSE": [{
                "programSeriesKey": "CS-SOFT",
                "programVersion": 2,
                "courseCode": "CS101",
                "courseVersion": 1,
                "openTermNo": 1,
                "module": "MAJOR_CORE",
                "formationMode": "ADMIN_FIXED",
                "creditSnapshot": "",
            }],
            "CREDIT_REQUIREMENT": [{
                "programSeriesKey": "CS-SOFT",
                "programVersion": 2,
                "module": "MAJOR_CORE",
                "creditTarget": "3",
            }],
            "GRADUATION": [{
                "programSeriesKey": "CS-SOFT",
                "programVersion": 2,
                "category": "ABILITY",
                "content": "完成专业综合项目并通过考核",
            }],
        }
    )


def _run(*, incoming_major: int, incoming_grade: str, predecessor_major: int, predecessor_grade: str):
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preflight_pipeline as pipeline

    forbidden_calls = {"definition": 0, "binding": 0}

    def forbidden_definition(_keys):
        forbidden_calls["definition"] += 1
        raise AssertionError("series scope drift must stop before child definition reads")

    def forbidden_binding(_keys):
        forbidden_calls["binding"] += 1
        raise AssertionError("DEFINITION scope drift must not reach binding-only reads")

    result = pipeline.run_program_import_preflight(
        _rows(major_id=incoming_major, grade_year=incoming_grade),
        phase="DEFINITION",
        load_allowed_major_ids=lambda: None,
        load_major_snapshots=lambda keys: [{
            "majorId": incoming_major,
            "educationYears": 3,
            "status": "ACTIVE",
        }],
        load_class_snapshots=lambda _keys: (_ for _ in ()).throw(
            AssertionError("DEFINITION must not load SchoolClass")
        ),
        load_course_snapshots=lambda keys: [{
            "courseId": 11,
            "courseCode": "CS101",
            "version": 1,
            "courseName": "Python程序设计",
            "credit": 3,
            "status": "ENABLED",
        }],
        load_program_snapshots=lambda keys: [{
            "programId": 501,
            "seriesKey": "CS-SOFT",
            "version": 1,
            "programName": "软件技术培养方案V1",
            "majorId": predecessor_major,
            "gradeYear": predecessor_grade,
            "totalCredits": 3,
            "prevVersionId": "",
            "status": "PUBLISHED",
        }],
        load_existing_definition_rows=forbidden_definition,
        load_program_status_by_id=forbidden_binding,
        load_active_binding_snapshots=forbidden_binding,
    )
    assert forbidden_calls == {"definition": 0, "binding": 0}
    return result


@pytest.mark.parametrize(
    "incoming_major,incoming_grade,predecessor_major,predecessor_grade,different_fields",
    [
        (20, "2026", 10, "2026", ("major",)),
        (10, "2027", 10, "2026", ("grade",)),
        (20, "2027", 10, "2026", ("major", "grade")),
    ],
)
def test_vn_create_rejects_incoming_major_or_grade_drift_before_quality_and_children(
    incoming_major,
    incoming_grade,
    predecessor_major,
    predecessor_grade,
    different_fields,
):
    result = _run(
        incoming_major=incoming_major,
        incoming_grade=incoming_grade,
        predecessor_major=predecessor_major,
        predecessor_grade=predecessor_grade,
    )

    assert result["stage"] == "REFERENCE"
    assert result["programPreflightSafe"] is False
    error = next(item for item in result["errors"] if item["businessCode"] == "PROGRAM_SERIES_SCOPE_DRIFT")
    assert error["evidence"] == {
        "predecessorProgramId": "501",
        "incomingMajorId": incoming_major,
        "predecessorMajorId": predecessor_major,
        "incomingGradeYear": incoming_grade,
        "predecessorGradeYear": predecessor_grade,
    }
    assert result["actions"] == [{
        "programKey": "SERIES:CS-SOFT:v2",
        "action": "CONFLICT",
        "programId": "",
        "createStatus": "DRAFT",
        "predecessorProgramId": "501",
        "requiresDefinitionReconciliation": False,
    }]


def test_continuity_guard_keeps_matching_vn_create_action_intact():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_series_continuity_guard as guard

    reference = {
        "referencePreflightSafe": True,
        "errors": [],
        "actions": [{
            "programKey": "SERIES:CS-SOFT:v2",
            "action": "CREATE",
            "programId": "",
            "createStatus": "DRAFT",
            "predecessorProgramId": "501",
            "requiresDefinitionReconciliation": False,
        }],
    }
    result = guard.enforce_program_series_continuity(
        _rows(major_id=10, grade_year="2026"),
        reference,
        program_snapshots=[{
            "programId": 501,
            "majorId": 10,
            "gradeYear": "2026",
        }],
    )
    assert result["referencePreflightSafe"] is True
    assert result["errors"] == []
    assert result["actions"] == reference["actions"]
