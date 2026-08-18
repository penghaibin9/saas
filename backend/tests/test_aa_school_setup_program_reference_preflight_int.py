"""INT Program authoritative-reference preflight contracts."""
from __future__ import annotations

import inspect

import pytest


def _adapter():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter
    return adapter


def _reference():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_reference_preflight as reference
    return reference


def _rows(*, series="CS-SOFT", version=1, education_years=3, open_term=1, binding=False, credit_snapshot=None):
    course = {
        "programSeriesKey": series, "programVersion": version,
        "courseCode": "CS101", "courseVersion": 1,
        "openTermNo": open_term, "module": "专业核心", "formationMode": "ADMIN_FIXED",
    }
    if credit_snapshot is not None:
        course["creditSnapshot"] = credit_snapshot
    grouped = {
        "MAIN": [{
            "programSeriesKey": series, "programVersion": version,
            "programName": "2026软件技术培养方案", "majorId": 10,
            "gradeYear": "2026", "totalCredits": 150,
            "educationYears": education_years,
        }],
        "COURSE": [course],
        "CREDIT_REQUIREMENT": [{
            "programSeriesKey": series, "programVersion": version,
            "module": "专业核心", "creditTarget": 150,
        }],
        "GRADUATION": [{
            "programSeriesKey": series, "programVersion": version,
            "category": "ABILITY", "content": "完成综合项目",
        }],
    }
    if binding:
        grouped["BINDING"] = [{
            "programSeriesKey": series, "programVersion": version,
            "majorId": 10, "gradeYear": "2026",
            "bindingScope": "CLASS", "classId": 77,
        }]
    return _adapter().normalize_program_import_rows(grouped)


def _majors(*, education_years=3, status="ACTIVE"):
    return [{"majorId": 10, "educationYears": education_years, "status": status}]


def _courses(*, status="ENABLED", credit="3.5"):
    return [{
        "courseId": 501, "courseCode": "CS101", "version": 1,
        "status": status, "credit": credit,
    }]


def test_reference_classifier_is_pure_and_does_not_open_database_or_write():
    source = inspect.getsource(_reference())
    for forbidden in (
        "get_sessionmaker", "session()", "db.query", "db.execute", "select(",
        "db.add", "db.commit", "db.flush", "ImportJob", "FileObject",
    ):
        assert forbidden not in source


def test_new_v1_with_green_major_and_exact_course_is_create_draft_candidate():
    result = _reference().program_import_reference_preflight(
        _rows(),
        major_snapshots=_majors(),
        course_snapshots=_courses(),
    )
    assert result["referencePreflightSafe"] is True
    assert result["errors"] == []
    assert result["actions"] == [{
        "programKey": "SERIES:CS-SOFT:v1",
        "action": "CREATE",
        "programId": "",
        "createStatus": "DRAFT",
        "predecessorProgramId": "",
        "requiresDefinitionReconciliation": False,
    }]


def test_exact_existing_program_is_only_reuse_candidate_until_children_reconcile():
    result = _reference().program_import_reference_preflight(
        _rows(),
        major_snapshots=_majors(),
        course_snapshots=_courses(),
        program_snapshots=[{
            "programId": 9001,
            "seriesKey": "CS-SOFT",
            "version": 1,
            "prevVersionId": None,
            "programName": "2026软件技术培养方案",
            "majorId": 10,
            "gradeYear": "2026",
            "totalCredits": 150,
            "status": "ENABLED",
        }],
    )
    assert result["referencePreflightSafe"] is True
    assert result["actions"] == [{
        "programKey": "SERIES:CS-SOFT:v1",
        "action": "REUSE",
        "programId": "9001",
        "requiresDefinitionReconciliation": True,
    }]


def test_direct_successor_requires_same_series_latest_predecessor_and_versionable_status():
    predecessor = {
        "programId": 9001,
        "seriesKey": "CS-SOFT",
        "version": 1,
        "prevVersionId": None,
        "programName": "旧版本",
        "majorId": 10,
        "gradeYear": "2026",
        "totalCredits": 140,
        "status": "ENABLED",
    }
    result = _reference().program_import_reference_preflight(
        _rows(version=2),
        major_snapshots=_majors(),
        course_snapshots=_courses(),
        program_snapshots=[predecessor],
    )
    assert result["referencePreflightSafe"] is True
    assert result["actions"][0] == {
        "programKey": "SERIES:CS-SOFT:v2",
        "action": "CREATE",
        "programId": "",
        "createStatus": "DRAFT",
        "predecessorProgramId": "9001",
        "requiresDefinitionReconciliation": False,
    }

    blocked = _reference().program_import_reference_preflight(
        _rows(version=2),
        major_snapshots=_majors(),
        course_snapshots=_courses(),
        program_snapshots=[dict(predecessor, status="DRAFT")],
    )
    assert blocked["referencePreflightSafe"] is False
    assert "PROGRAM_PREDECESSOR_NOT_VERSIONABLE" in {
        item["businessCode"] for item in blocked["errors"]
    }


def test_v3_only_current_snapshot_cannot_fabricate_missing_v2():
    result = _reference().program_import_reference_preflight(
        _rows(version=3),
        major_snapshots=_majors(),
        course_snapshots=_courses(),
        program_snapshots=[{
            "programId": 9001, "seriesKey": "CS-SOFT", "version": 1,
            "prevVersionId": None, "majorId": 10, "gradeYear": "2026",
            "programName": "v1", "totalCredits": 150, "status": "ENABLED",
        }],
    )
    assert result["referencePreflightSafe"] is False
    issue = next(item for item in result["errors"] if item["businessCode"] == "PROGRAM_PREDECESSOR_MISSING")
    assert issue["evidence"]["requiredPredecessorKey"] == "SERIES:CS-SOFT:v2"
    assert "不得为 v3-only" in issue["howToResolve"]


def test_major_education_years_is_authority_and_source_assertion_never_overwrites_it():
    result = _reference().program_import_reference_preflight(
        _rows(education_years=4),
        major_snapshots=_majors(education_years=3),
        course_snapshots=_courses(),
    )
    issue = next(
        item for item in result["errors"]
        if item["businessCode"] == "PROGRAM_EDUCATION_YEARS_ASSERTION_MISMATCH"
    )
    assert issue["evidence"] == {
        "majorId": 10,
        "sourceEducationYears": 4,
        "majorEducationYears": 3,
    }
    assert "唯一学制真值" in issue["howToResolve"]


def test_major_scope_and_major_term_limit_are_enforced():
    out_of_scope = _reference().program_import_reference_preflight(
        _rows(),
        major_snapshots=_majors(),
        course_snapshots=_courses(),
        allowed_major_ids=set(),
    )
    assert "PROGRAM_MAJOR_OUT_OF_SCOPE" in {item["businessCode"] for item in out_of_scope["errors"]}

    term_overflow = _reference().program_import_reference_preflight(
        _rows(education_years=4, open_term=7),
        major_snapshots=_majors(education_years=3),
        course_snapshots=_courses(),
    )
    assert "PROGRAM_OPEN_TERM_EXCEEDS_MAJOR_EDUCATION_YEARS" in {
        item["businessCode"] for item in term_overflow["errors"]
    }


def test_exact_course_version_must_be_enabled_and_credit_snapshot_is_assertion_only():
    missing = _reference().program_import_reference_preflight(
        _rows(), major_snapshots=_majors(), course_snapshots=[]
    )
    assert "PROGRAM_COURSE_VERSION_NOT_FOUND" in {item["businessCode"] for item in missing["errors"]}

    disabled = _reference().program_import_reference_preflight(
        _rows(), major_snapshots=_majors(), course_snapshots=_courses(status="DISABLED")
    )
    assert "PROGRAM_COURSE_VERSION_NOT_ENABLED" in {item["businessCode"] for item in disabled["errors"]}

    mismatch = _reference().program_import_reference_preflight(
        _rows(credit_snapshot="4"), major_snapshots=_majors(), course_snapshots=_courses(credit="3.5")
    )
    issue = next(
        item for item in mismatch["errors"]
        if item["businessCode"] == "PROGRAM_COURSE_CREDIT_ASSERTION_MISMATCH"
    )
    assert issue["evidence"]["courseCredit"] == "3.5"


def test_class_binding_must_match_program_major_grade_and_normal_class():
    green = _reference().program_import_reference_preflight(
        _rows(binding=True),
        major_snapshots=_majors(),
        course_snapshots=_courses(),
        class_snapshots=[{
            "classId": 77, "majorId": 10, "gradeYear": "2026", "classStatus": "NORMAL",
        }],
    )
    assert green["referencePreflightSafe"] is True

    bad = _reference().program_import_reference_preflight(
        _rows(binding=True),
        major_snapshots=_majors(),
        course_snapshots=_courses(),
        class_snapshots=[{
            "classId": 77, "majorId": 11, "gradeYear": "2025", "classStatus": "GRADUATED",
        }],
    )
    assert {
        "PROGRAM_BINDING_CLASS_SCOPE_MISMATCH",
        "PROGRAM_BINDING_CLASS_INACTIVE",
    } <= {item["businessCode"] for item in bad["errors"]}


def test_existing_program_snapshots_without_series_key_fail_closed_until_schema_backfill():
    with pytest.raises(ValueError, match="seriesKey"):
        _reference().program_import_reference_preflight(
            _rows(),
            major_snapshots=_majors(),
            course_snapshots=_courses(),
            program_snapshots=[{
                "programId": 9001, "version": 1, "prevVersionId": None,
                "majorId": 10, "gradeYear": "2026", "status": "ENABLED",
            }],
        )
