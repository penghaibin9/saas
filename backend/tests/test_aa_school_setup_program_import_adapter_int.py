"""INT Program six-group pure adapter contracts."""
from __future__ import annotations

import inspect

import pytest


def _adapter():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter
    return adapter


def _main(**overrides):
    row = {
        "programSeriesKey": "CS-SOFT",
        "programVersion": 2,
        "programName": "2026软件技术人才培养方案",
        "majorId": 10,
        "gradeYear": "2026",
        "totalCredits": "150.5",
        "educationYears": 3,
    }
    row.update(overrides)
    return row


def test_program_adapter_is_pure_and_has_no_shared_file_or_db_lifecycle():
    source = inspect.getsource(_adapter())
    for forbidden in (
        "get_sessionmaker", "session()", "db.query", "db.execute", "db.add",
        "db.commit", "ImportJob", "FileObject", "xlsx_util", "openpyxl",
    ):
        assert forbidden not in source


def test_main_row_uses_explicit_series_identity_and_keeps_education_years_assertion_only():
    item = _adapter().normalize_program_import_row("main", _main(), row_no=2)
    assert item["logicalGroup"] == "MAIN"
    assert item["programKey"] == "SERIES:CS-SOFT:v2"
    assert item["definitionKey"] == "SERIES:CS-SOFT:v2"
    assert item["payload"] == {
        "programSeriesKey": "CS-SOFT",
        "programVersion": 2,
        "programName": "2026软件技术人才培养方案",
        "majorId": 10,
        "gradeYear": "2026",
        "totalCredits": item["payload"]["totalCredits"],
        "educationYearsAssertion": 3,
    }
    assert str(item["payload"]["totalCredits"]) == "150.5"


def test_main_row_never_derives_identity_from_major_grade_or_name():
    first = _adapter().normalize_program_import_row("MAIN", _main(), row_no=2)
    second = _adapter().normalize_program_import_row(
        "MAIN",
        _main(
            programSeriesKey="CS-SOFT-ALT",
            programName="同专业同年级同版本并行方案",
        ),
        row_no=3,
    )
    assert first["payload"]["majorId"] == second["payload"]["majorId"] == 10
    assert first["payload"]["gradeYear"] == second["payload"]["gradeYear"] == "2026"
    assert first["programKey"] != second["programKey"]


@pytest.mark.parametrize("grade", ["26", "202A", "20260", ""])
def test_main_grade_year_is_an_assertion_but_still_strictly_validated(grade):
    with pytest.raises(ValueError, match="gradeYear"):
        _adapter().normalize_program_import_row("MAIN", _main(gradeYear=grade), row_no=2)


def test_course_row_requires_exact_course_version_module_and_explicit_formation():
    item = _adapter().normalize_program_import_row(
        "COURSE",
        {
            "programSeriesKey": "CS-SOFT",
            "programVersion": 2,
            "courseCode": " cs101 ",
            "courseVersion": 3,
            "openTermNo": 4,
            "module": "专业核心",
            "formationMode": "selectable",
            "creditSnapshot": "3.5",
        },
        row_no=5,
    )
    assert item["programKey"] == "SERIES:CS-SOFT:v2"
    assert item["definitionKey"] == "SERIES:CS-SOFT:v2|COURSE|CS101@v3"
    assert item["payload"]["courseKey"] == "CS101@v3"
    assert item["payload"]["module"] == "专业核心"
    assert item["payload"]["formationMode"] == "SELECTABLE"


def test_credit_practice_graduation_and_binding_rows_are_deterministic():
    adapter = _adapter()
    credit = adapter.normalize_program_import_row(
        "CREDIT_REQUIREMENT",
        {
            "programSeriesKey": "CS-SOFT", "programVersion": 2,
            "module": "专业核心", "creditTarget": "30",
        },
        row_no=2,
    )
    practice = adapter.normalize_program_import_row(
        "PRACTICE",
        {
            "programSeriesKey": "CS-SOFT", "programVersion": 2,
            "segmentName": "岗位实习", "segmentType": "POST_INTERNSHIP",
            "openTermNo": 5, "weeks": 16, "credit": 8,
            "orgMode": "DISTRIBUTED", "assessmentMode": "CHECK", "sortOrder": 10,
        },
        row_no=2,
    )
    graduation = adapter.normalize_program_import_row(
        "GRADUATION",
        {
            "programSeriesKey": "CS-SOFT", "programVersion": 2,
            "category": "ABILITY", "content": "完成综合项目", "sortOrder": 1,
        },
        row_no=2,
    )
    binding = adapter.normalize_program_import_row(
        "BINDING",
        {
            "programSeriesKey": "CS-SOFT", "programVersion": 2,
            "majorId": 10, "gradeYear": "2026",
            "bindingScope": "CLASS", "classId": 77,
        },
        row_no=2,
    )

    assert credit["definitionKey"] == "SERIES:CS-SOFT:v2|CREDIT|专业核心"
    assert practice["definitionKey"] == "SERIES:CS-SOFT:v2|PRACTICE|POST_INTERNSHIP|岗位实习|5"
    assert practice["payload"]["sortOrder"] == 10
    assert graduation["definitionKey"] == "SERIES:CS-SOFT:v2|GRADUATION|ABILITY|完成综合项目"
    assert binding["definitionKey"] == "SERIES:CS-SOFT:v2|MAJOR:10:GRADE:2026:CLASS:77"
    assert binding["payload"]["classId"] == 77


def test_grouped_normalization_uses_fixed_group_order_and_sheet_local_row_numbers():
    adapter = _adapter()
    items = adapter.normalize_program_import_rows({
        "BINDING": [{
            "programSeriesKey": "CS-SOFT", "programVersion": 2,
            "majorId": 10, "gradeYear": "2026", "bindingScope": "MAJOR_GRADE",
        }],
        "MAIN": [_main()],
        "COURSE": [{
            "programSeriesKey": "CS-SOFT", "programVersion": 2,
            "courseCode": "CS101", "courseVersion": 1,
            "openTermNo": 1, "module": "专业核心", "formationMode": "ADMIN_FIXED",
        }],
    })
    assert [item["logicalGroup"] for item in items] == ["MAIN", "COURSE", "BINDING"]
    assert [item["rowNo"] for item in items] == [2, 2, 2]


def test_unknown_group_missing_required_fields_and_invalid_row_numbers_fail_closed():
    adapter = _adapter()
    with pytest.raises(ValueError, match="unsupported logicalGroup"):
        adapter.normalize_program_import_row("LEGACY_FLAT", _main(), row_no=2)
    with pytest.raises(ValueError, match="missing required fields"):
        adapter.normalize_program_import_row("COURSE", {
            "programSeriesKey": "CS-SOFT", "programVersion": 2,
        }, row_no=2)
    with pytest.raises(ValueError, match="row_no"):
        adapter.normalize_program_import_row("MAIN", _main(), row_no=0)
    with pytest.raises(ValueError, match="unsupported logical groups"):
        adapter.normalize_program_import_rows({"UNKNOWN": [_main()]})
