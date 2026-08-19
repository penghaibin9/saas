"""A-W4 duplicate-source ordering guard for Course dry-run bridge."""
from __future__ import annotations


def _row(*, college: str, teacher: str) -> dict:
    return {
        "courseCode": "CS101",
        "version": "1",
        "courseName": "Python程序设计",
        "category": "MAJOR_CORE",
        "nature": "REQUIRED",
        "credit": "3",
        "hoursTotal": "48",
        "hoursTheory": "32",
        "hoursPractice": "16",
        "hoursExperiment": "",
        "hoursComputer": "",
        "examMode": "EXAM",
        "ownerCollegeId": college,
        "ownerTeacherId": teacher,
        "isCore": "是",
        "prerequisiteCodes": "",
    }


def test_duplicate_business_key_rejects_every_occurrence_before_reference_queries():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_course_preflight_service as bridge

    # The first duplicate also carries invalid references. Duplicate identity must
    # win before owner validation; otherwise filtering one row could hide the
    # duplicate and let the second row become CREATE/REUSE by accident.
    result = bridge.course_catalog_dry_run(
        [
            _row(college="999999", teacher="999999"),
            _row(college="17", teacher="81"),
        ],
        {"currentRoleCode": "ACADEMIC_ADMIN"},
    )

    assert result["totalRows"] == 2
    assert result["validRows"] == 0
    assert result["rejectRows"] == 2
    assert result["invalidRows"] == 2
    assert {item["code"] for item in result["items"]} == {"DUPLICATE_SOURCE_KEY"}
    assert [item["row"] for item in result["items"]] == [2, 3]
    assert len(result["errors"]) == 2
