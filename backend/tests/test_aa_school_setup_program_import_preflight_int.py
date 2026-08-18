"""INT source-only Program preflight contracts."""
from __future__ import annotations

import inspect


def _adapter():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter
    return adapter


def _preflight():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_preflight as preflight
    return preflight


def _valid_rows(*, education_years=3, course_term=1, target="150"):
    grouped = {
        "MAIN": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 1,
            "programName": "2026软件技术培养方案",
            "majorId": 10,
            "gradeYear": "2026",
            "totalCredits": "150",
            "educationYears": education_years,
        }],
        "COURSE": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 1,
            "courseCode": "CS101",
            "courseVersion": 1,
            "openTermNo": course_term,
            "module": "专业核心",
            "formationMode": "ADMIN_FIXED",
        }],
        "CREDIT_REQUIREMENT": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 1,
            "module": "专业核心",
            "creditTarget": target,
        }],
        "GRADUATION": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 1,
            "category": "ABILITY",
            "content": "完成综合项目并形成可审计成果",
        }],
    }
    return _adapter().normalize_program_import_rows(grouped)


def test_source_preflight_is_zero_db_and_zero_file_lifecycle():
    source = inspect.getsource(_preflight())
    for forbidden in (
        "get_sessionmaker", "session()", "db.query", "db.execute", "select(",
        "ImportJob", "FileObject", "xlsx_util", "openpyxl",
    ):
        assert forbidden not in source


def test_valid_minimum_program_definition_passes_without_binding_or_practice():
    result = _preflight().program_import_source_preflight(_valid_rows())
    assert result == {
        "totalRows": 4,
        "programCount": 1,
        "invalidRows": 0,
        "blockerCount": 0,
        "sourcePreflightSafe": True,
        "errors": [],
    }


def test_child_without_main_fails_closed_instead_of_inventing_program_identity():
    rows = _adapter().normalize_program_import_rows({
        "COURSE": [{
            "programSeriesKey": "CS-SOFT", "programVersion": 3,
            "courseCode": "CS101", "courseVersion": 1,
            "openTermNo": 1, "module": "专业核心", "formationMode": "ADMIN_FIXED",
        }],
    })
    result = _preflight().program_import_source_preflight(rows)
    assert result["sourcePreflightSafe"] is False
    assert [item["businessCode"] for item in result["errors"]] == ["PROGRAM_MAIN_MISSING"]
    assert result["errors"][0]["programKey"] == "SERIES:CS-SOFT:v3"


def test_duplicate_definition_is_not_resolved_by_row_order():
    rows = _valid_rows()
    course = next(row for row in rows if row["logicalGroup"] == "COURSE")
    duplicate = dict(course)
    duplicate["rowNo"] = 9
    result = _preflight().program_import_source_preflight([*rows, duplicate])
    codes = [item["businessCode"] for item in result["errors"]]
    assert codes.count("PROGRAM_SOURCE_DUPLICATE_DEFINITION") == 2
    assert result["sourcePreflightSafe"] is False
    duplicate_errors = [
        item for item in result["errors"]
        if item["businessCode"] == "PROGRAM_SOURCE_DUPLICATE_DEFINITION"
    ]
    assert {item["row"] for item in duplicate_errors} == {2, 9}
    assert all(item["evidence"]["occurrences"] == 2 for item in duplicate_errors)


def test_missing_course_credit_structure_and_graduation_are_independent_blockers():
    rows = _adapter().normalize_program_import_rows({
        "MAIN": [{
            "programSeriesKey": "CS-SOFT", "programVersion": 1,
            "programName": "方案", "majorId": 10, "gradeYear": "2026", "totalCredits": 150,
        }],
    })
    result = _preflight().program_import_source_preflight(rows)
    assert {item["businessCode"] for item in result["errors"]} == {
        "PROGRAM_COURSE_EMPTY",
        "PROGRAM_CREDIT_REQUIREMENT_EMPTY",
        "PROGRAM_GRADUATION_REQUIREMENT_EMPTY",
    }
    assert result["blockerCount"] == 3


def test_source_education_years_only_catches_impossible_term_and_never_becomes_org_writer():
    result = _preflight().program_import_source_preflight(
        _valid_rows(education_years=3, course_term=7)
    )
    issue = next(
        item for item in result["errors"]
        if item["businessCode"] == "PROGRAM_OPEN_TERM_EXCEEDS_SOURCE_EDUCATION_YEARS"
    )
    assert issue["evidence"] == {
        "openTermNo": 7,
        "educationYearsAssertion": 3,
        "maxTermNo": 6,
    }
    assert "数据库学制不会被导入修改" in issue["howToResolve"]


def test_credit_target_sum_and_course_module_are_checked_from_source_only():
    rows = _valid_rows(target="140")
    course = next(row for row in rows if row["logicalGroup"] == "COURSE")
    course["payload"] = dict(course["payload"], module="未声明模块")
    result = _preflight().program_import_source_preflight(rows)
    assert {item["businessCode"] for item in result["errors"]} == {
        "PROGRAM_CREDIT_TARGET_SUM_MISMATCH",
        "PROGRAM_COURSE_MODULE_UNDECLARED",
    }
    mismatch = next(
        item for item in result["errors"]
        if item["businessCode"] == "PROGRAM_CREDIT_TARGET_SUM_MISMATCH"
    )
    assert mismatch["evidence"] == {"creditTargetSum": "140", "totalCredits": "150"}


def test_two_explicit_series_are_counted_separately_even_with_same_major_grade_version():
    adapter = _adapter()
    first = _valid_rows()
    second = adapter.normalize_program_import_rows({
        "MAIN": [{
            "programSeriesKey": "CS-SOFT-ALT", "programVersion": 1,
            "programName": "并行方案", "majorId": 10, "gradeYear": "2026", "totalCredits": 150,
        }],
        "COURSE": [{
            "programSeriesKey": "CS-SOFT-ALT", "programVersion": 1,
            "courseCode": "CS102", "courseVersion": 1,
            "openTermNo": 1, "module": "专业核心", "formationMode": "ADMIN_FIXED",
        }],
        "CREDIT_REQUIREMENT": [{
            "programSeriesKey": "CS-SOFT-ALT", "programVersion": 1,
            "module": "专业核心", "creditTarget": 150,
        }],
        "GRADUATION": [{
            "programSeriesKey": "CS-SOFT-ALT", "programVersion": 1,
            "category": "ABILITY", "content": "并行培养目标",
        }],
    })
    result = _preflight().program_import_source_preflight([*first, *second])
    assert result["sourcePreflightSafe"] is True
    assert result["programCount"] == 2
