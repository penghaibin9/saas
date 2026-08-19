"""A-W4 Course Catalog adapter contracts before File Exchange DB dry-run."""
from __future__ import annotations

import inspect

import pytest


def _adapter():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_import_adapter as adapter
    return adapter


def _row(**changes):
    row = {
        "courseCode": "CS101",
        "version": "1",
        "courseName": "Python程序设计",
        "category": "MAJOR_CORE",
        "nature": "REQUIRED",
        "credit": "3.5",
        "hoursTotal": "48",
        "hoursTheory": "32",
        "hoursPractice": "16",
        "hoursExperiment": "",
        "hoursComputer": "",
        "examMode": "EXAM",
        "ownerCollegeId": "17",
        "ownerTeacherId": "81",
        "isCore": "是",
        "description": "课程简介",
        "prerequisiteCodes": "MATH101， ENG101;MATH101",
    }
    row.update(changes)
    return row


def test_course_adapter_is_pure_domain_normalization_not_second_import_framework():
    source = inspect.getsource(_adapter())
    for forbidden in (
        "ImportJob(", "FileObject(", "get_sessionmaker", "session()", "db.commit", "load_workbook",
    ):
        assert forbidden not in source


def test_course_adapter_normalizes_existing_course_writer_shape_and_stable_identity():
    result = _adapter().normalize_course_import_row(_row(), row_no=2)
    assert result["rowNo"] == 2
    assert result["businessKey"] == "CS101@v1"
    assert result["courseCode"] == "CS101"
    assert result["version"] == 1
    assert result["payload"] == {
        "courseCode": "CS101",
        "courseName": "Python程序设计",
        "courseNameEn": None,
        "category": "MAJOR_CORE",
        "nature": "REQUIRED",
        "credit": 3.5,
        "hoursTotal": 48,
        "hoursTheory": 32,
        "hoursPractice": 16,
        "hoursExperiment": None,
        "hoursComputer": None,
        "examMode": "EXAM",
        "ownerCollegeId": 17,
        "ownerTeacherId": 81,
        "isCore": True,
        "description": "课程简介",
        "prerequisiteCodes": ["MATH101", "ENG101"],
    }


def test_course_adapter_name_change_never_changes_business_identity():
    adapter = _adapter()
    original = adapter.normalize_course_import_row(_row(courseName="旧名称"), row_no=2)
    renamed = adapter.normalize_course_import_row(_row(courseName="新名称"), row_no=3)
    same_name_other_code = adapter.normalize_course_import_row(
        _row(courseCode="CS102", courseName="旧名称"), row_no=4
    )
    assert original["businessKey"] == renamed["businessKey"] == "CS101@v1"
    assert same_name_other_code["businessKey"] == "CS102@v1"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("courseCode", "python", "courseCode format"),
        ("category", "UNKNOWN", "unsupported category"),
        ("nature", "UNKNOWN", "unsupported nature"),
        ("examMode", "UNKNOWN", "unsupported examMode"),
        ("credit", "-1", "credit must be non-negative"),
        ("ownerCollegeId", "0", "ownerCollegeId"),
        ("ownerTeacherId", "abc", "ownerTeacherId"),
        ("isCore", "maybe", "isCore must be yes/no"),
    ],
)
def test_course_adapter_rejects_invalid_domain_values(field, value, message):
    with pytest.raises(ValueError, match=message):
        _adapter().normalize_course_import_row(_row(**{field: value}), row_no=2)


def test_course_adapter_rejects_hour_component_mismatch_before_db_dry_run():
    with pytest.raises(ValueError, match="hour components sum"):
        _adapter().normalize_course_import_row(
            _row(hoursTotal="48", hoursTheory="30", hoursPractice="10"), row_no=2
        )


def test_course_adapter_rejects_invalid_prerequisite_stable_code():
    with pytest.raises(ValueError, match="invalid prerequisite courseCode"):
        _adapter().normalize_course_import_row(_row(prerequisiteCodes="MATH101,课程A"), row_no=2)


def test_course_adapter_uses_xlsx_row_numbers_starting_at_two():
    rows = [_row(courseCode="CS101"), _row(courseCode="CS102")]
    normalized = _adapter().normalize_course_import_rows(rows)
    assert [(item["rowNo"], item["businessKey"]) for item in normalized] == [
        (2, "CS101@v1"),
        (3, "CS102@v1"),
    ]
