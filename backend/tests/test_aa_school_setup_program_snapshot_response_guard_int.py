"""INT negative contracts for Program snapshot loader response bounds."""
from __future__ import annotations

import pytest


def _guard():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_snapshot_response_guard as guard
    return guard


def test_major_and_class_loader_overfetch_fail_closed():
    guard = _guard()
    with pytest.raises(RuntimeError, match="PROGRAM_SNAPSHOT_SCOPE_VIOLATION:MAJOR"):
        guard.guard_major_snapshots(
            [{"majorId": 10}, {"majorId": 99}],
            (10,),
        )
    with pytest.raises(RuntimeError, match="PROGRAM_SNAPSHOT_SCOPE_VIOLATION:CLASS"):
        guard.guard_class_snapshots(
            [{"classId": 77}, {"classId": 88}],
            (77,),
        )


def test_course_and_program_series_loader_overfetch_fail_closed():
    guard = _guard()
    with pytest.raises(RuntimeError, match="PROGRAM_SNAPSHOT_SCOPE_VIOLATION:COURSE"):
        guard.guard_course_snapshots(
            [
                {"courseCode": "CS101", "version": 1},
                {"courseCode": "CS999", "version": 1},
            ],
            ("CS101@v1",),
        )
    with pytest.raises(RuntimeError, match="PROGRAM_SNAPSHOT_SCOPE_VIOLATION:PROGRAM_SERIES"):
        guard.guard_program_snapshots(
            [{"seriesKey": "SER-A"}, {"seriesKey": "SER-B"}],
            ("SER-A",),
        )


def test_definition_and_status_loader_overfetch_fail_closed():
    guard = _guard()
    with pytest.raises(RuntimeError, match="PROGRAM_SNAPSHOT_SCOPE_VIOLATION:PROGRAM_DEFINITION"):
        guard.guard_definition_snapshots(
            [{"programId": 501}, {"programId": 999}],
            ("501",),
        )
    with pytest.raises(RuntimeError, match="PROGRAM_SNAPSHOT_SCOPE_VIOLATION:PROGRAM_STATUS"):
        guard.guard_program_status_by_id(
            {"501": "PUBLISHED", "999": "PUBLISHED"},
            ("501",),
        )


def test_active_binding_loader_overfetch_fail_closed_for_explicit_or_derived_scope_key():
    guard = _guard()
    with pytest.raises(RuntimeError, match="PROGRAM_SNAPSHOT_SCOPE_VIOLATION:ACTIVE_BINDING"):
        guard.guard_active_binding_snapshots(
            [{"scopeKey": "MAJOR:1:GRADE:2026:MAJOR_GRADE", "programId": 1},
             {"scopeKey": "MAJOR:2:GRADE:2026:MAJOR_GRADE", "programId": 2}],
            ("MAJOR:1:GRADE:2026:MAJOR_GRADE",),
        )
    with pytest.raises(RuntimeError, match="PROGRAM_SNAPSHOT_SCOPE_VIOLATION:ACTIVE_BINDING"):
        guard.guard_active_binding_snapshots(
            [{
                "majorId": 1,
                "gradeYear": "2026",
                "bindingScope": "CLASS",
                "classId": 99,
                "programId": 2,
            }],
            ("MAJOR:1:GRADE:2026:CLASS:77",),
        )


def test_missing_requested_snapshot_is_not_an_overfetch_violation():
    guard = _guard()
    assert guard.guard_major_snapshots([], (10,)) == []
    assert guard.guard_course_snapshots([], ("CS101@v1",)) == []
    assert guard.guard_program_snapshots([], ("SER-A",)) == []
    assert guard.guard_definition_snapshots([], ("501",)) == []
    assert guard.guard_program_status_by_id({}, ("501",)) == {}
    assert guard.guard_active_binding_snapshots([], ("MAJOR:1:GRADE:2026:MAJOR_GRADE",)) == []


def test_pipeline_rejects_overfetched_major_before_reference_classifier_consumes_it():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preflight_pipeline as pipeline

    rows = [
        {
            "rowNo": 2,
            "logicalGroup": "MAIN",
            "programKey": "SERIES:SER-A:v1",
            "definitionKey": "SERIES:SER-A:v1",
            "payload": {
                "programSeriesKey": "SER-A", "programVersion": 1,
                "programName": "方案", "majorId": 1, "gradeYear": "2026",
                "totalCredits": 3,
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "COURSE",
            "programKey": "SERIES:SER-A:v1",
            "definitionKey": "SERIES:SER-A:v1|COURSE|CS101@v1",
            "payload": {
                "programKey": "SERIES:SER-A:v1", "courseKey": "CS101@v1",
                "module": "核心", "formationMode": "ADMIN_FIXED", "openTermNo": 1,
                "creditSnapshot": None,
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "CREDIT_REQUIREMENT",
            "programKey": "SERIES:SER-A:v1",
            "definitionKey": "SERIES:SER-A:v1|CREDIT|核心",
            "payload": {"programKey": "SERIES:SER-A:v1", "module": "核心", "creditTarget": 3},
        },
        {
            "rowNo": 2,
            "logicalGroup": "GRADUATION",
            "programKey": "SERIES:SER-A:v1",
            "definitionKey": "SERIES:SER-A:v1|GRADUATION|ABILITY|目标",
            "payload": {"programKey": "SERIES:SER-A:v1", "category": "ABILITY", "content": "目标", "sortOrder": 0},
        },
    ]

    with pytest.raises(RuntimeError, match="PROGRAM_SNAPSHOT_SCOPE_VIOLATION:MAJOR"):
        pipeline.run_program_import_preflight(
            rows,
            phase="DEFINITION",
            load_allowed_major_ids=lambda: None,
            load_major_snapshots=lambda _keys: [
                {"majorId": 1, "educationYears": 3, "status": "ACTIVE"},
                {"majorId": 999, "educationYears": 3, "status": "ACTIVE"},
            ],
            load_class_snapshots=lambda _keys: [],
            load_course_snapshots=lambda _keys: [{
                "courseId": 101, "courseCode": "CS101", "version": 1,
                "status": "ENABLED", "credit": 3,
            }],
            load_program_snapshots=lambda _keys: [],
            load_existing_definition_rows=lambda _keys: [],
            load_program_status_by_id=lambda _keys: {},
            load_active_binding_snapshots=lambda _keys: [],
        )
