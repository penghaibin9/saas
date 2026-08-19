"""A-W4 Course Catalog dry-run classification contracts."""
from __future__ import annotations

import inspect

import pytest


def _preflight():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_import_preflight as preflight
    return preflight


def _incoming(*, code="CS101", version=1, name="Python程序设计", college=17, **payload_changes):
    payload = {
        "courseCode": code,
        "courseName": name,
        "courseNameEn": None,
        "category": "MAJOR_CORE",
        "nature": "REQUIRED",
        "credit": 3.0,
        "hoursTotal": 48,
        "hoursTheory": 32,
        "hoursPractice": 16,
        "hoursExperiment": None,
        "hoursComputer": None,
        "examMode": "EXAM",
        "ownerCollegeId": college,
        "ownerTeacherId": 81,
        "isCore": True,
        "description": None,
        "prerequisiteCodes": ["MATH101"],
    }
    payload.update(payload_changes)
    return {
        "rowNo": 2,
        "businessKey": f"{code}@v{version}",
        "courseCode": code,
        "version": version,
        "payload": payload,
    }


def _default_course_id(code: str, version: int) -> int:
    return (sum(ord(ch) for ch in code.upper()) * 100) + int(version)


def _existing(
    *,
    code="CS101",
    version=1,
    status="ENABLED",
    name="Python程序设计",
    course_id=None,
    prev_version_id="AUTO",
    **payload_changes,
):
    row = _incoming(code=code, version=version, name=name, **payload_changes)
    resolved_id = int(course_id or _default_course_id(code, version))
    if prev_version_id == "AUTO":
        resolved_prev = None if int(version) == 1 else _default_course_id(code, int(version) - 1)
    else:
        resolved_prev = prev_version_id
    return {
        "courseId": resolved_id,
        "courseCode": code,
        "version": version,
        "prevVersionId": resolved_prev,
        "status": status,
        "payload": row["payload"],
    }


def test_preflight_is_pure_classifier_without_db_or_file_framework():
    source = inspect.getsource(_preflight())
    for forbidden in ("select(", "session()", "get_sessionmaker", "db.commit", "ImportJob(", "FileObject("):
        assert forbidden not in source


def test_new_code_v1_is_create_and_same_fact_is_reuse():
    preflight = _preflight()
    create = preflight.course_catalog_preflight([_incoming()], [])
    assert create["createRows"] == 1
    assert create["invalidRows"] == 0
    assert create["items"][0]["action"] == "CREATE"

    reuse = preflight.course_catalog_preflight([_incoming()], [_existing()])
    assert reuse["reuseRows"] == 1
    assert reuse["invalidRows"] == 0
    assert reuse["items"][0]["action"] == "REUSE"


def test_same_stable_key_name_change_is_conflict_never_name_overwrite():
    result = _preflight().course_catalog_preflight(
        [_incoming(name="新名称")],
        [_existing(name="旧名称")],
    )
    assert result["conflictRows"] == 1
    assert result["items"][0]["action"] == "CONFLICT"
    assert result["items"][0]["code"] == "COURSE_STABLE_KEY_CONFLICT"
    assert "courseName" in result["items"][0]["evidence"]["differentFields"]


def test_same_name_different_course_code_does_not_become_identity_conflict():
    result = _preflight().course_catalog_preflight(
        [_incoming(code="CS102", name="同名课程")],
        [_existing(code="CS101", name="同名课程")],
    )
    assert result["items"][0]["action"] == "CREATE"
    assert result["items"][0]["businessKey"] == "CS102@v1"


def test_enabled_direct_successor_is_create_but_requested_gap_is_reject():
    preflight = _preflight()
    existing = [_existing(version=1, status="ENABLED")]
    successor = preflight.course_catalog_preflight([_incoming(version=2)], existing)
    assert successor["items"][0]["action"] == "CREATE"
    assert successor["items"][0]["code"] == "COURSE_SUCCESSOR_CREATE"

    gap = preflight.course_catalog_preflight([_incoming(version=3)], existing)
    assert gap["items"][0]["action"] == "REJECT"
    assert gap["items"][0]["code"] == "COURSE_VERSION_GAP"


def test_new_course_cannot_start_from_non_v1():
    result = _preflight().course_catalog_preflight([_incoming(version=2)], [])
    assert result["items"][0]["action"] == "REJECT"
    assert result["items"][0]["code"] == "COURSE_PREDECESSOR_MISSING"


def test_non_enabled_predecessor_blocks_parallel_successor():
    result = _preflight().course_catalog_preflight(
        [_incoming(version=2)],
        [_existing(version=1, status="DRAFT")],
    )
    assert result["items"][0]["action"] == "CONFLICT"
    assert result["items"][0]["code"] == "COURSE_PREDECESSOR_NOT_ENABLED"


def test_disabled_exact_version_is_conflict_not_reuse_or_revival():
    result = _preflight().course_catalog_preflight(
        [_incoming()],
        [_existing(status="DISABLED")],
    )
    assert result["items"][0]["action"] == "CONFLICT"
    assert result["items"][0]["code"] == "COURSE_VERSION_DISABLED"


def test_duplicate_stable_key_inside_same_source_rejects_all_occurrences():
    first = _incoming()
    second = {**_incoming(name="另一名称"), "rowNo": 3}
    result = _preflight().course_catalog_preflight([first, second], [])
    assert result["rejectRows"] == 2
    assert result["validRows"] == 0
    assert {item["code"] for item in result["items"]} == {"DUPLICATE_SOURCE_KEY"}


def test_college_scope_is_fail_closed_before_domain_confirm():
    preflight = _preflight()
    out_of_scope = preflight.course_catalog_preflight(
        [_incoming(college=18)],
        [],
        allowed_college_ids={17},
    )
    assert out_of_scope["items"][0]["action"] == "REJECT"
    assert out_of_scope["items"][0]["code"] == "COURSE_OWNER_OUT_OF_SCOPE"
    assert out_of_scope["invalidRows"] == 1

    missing_owner = preflight.course_catalog_preflight(
        [_incoming(college=None)],
        [],
        allowed_college_ids={17},
    )
    assert missing_owner["items"][0]["code"] == "COURSE_OWNER_OUT_OF_SCOPE"


def test_preflight_reconciliation_counts_and_errors_are_file_exchange_ready():
    rows = [
        _incoming(code="CS101", version=1),
        {**_incoming(code="CS102", version=1), "rowNo": 3},
        {**_incoming(code="CS103", version=2), "rowNo": 4},
        {**_incoming(code="CS104", version=1), "rowNo": 5},
    ]
    existing = [
        _existing(code="CS101", version=1),
        _existing(code="CS102", version=1, name="数据库名称"),
        _existing(code="CS104", version=1, status="DISABLED"),
    ]
    result = _preflight().course_catalog_preflight(rows, existing)
    assert result["totalRows"] == 4
    assert result["createRows"] == 0
    assert result["reuseRows"] == 1
    assert result["conflictRows"] == 2
    assert result["rejectRows"] == 1
    assert result["validRows"] == 1
    assert result["invalidRows"] == 3
    assert len(result["errors"]) == 3
    assert all({"row", "field", "code", "message", "evidence", "howToResolve"} <= set(item) for item in result["errors"])


def test_corrupt_existing_duplicate_stable_key_fails_closed():
    with pytest.raises(ValueError, match="duplicate existing Course stable key"):
        _preflight().course_catalog_preflight(
            [_incoming()],
            [_existing(), _existing(course_id=99999)],
        )


def test_corrupt_existing_chain_gap_fails_closed_before_row_classification():
    with pytest.raises(ValueError, match="version chain gap"):
        _preflight().course_catalog_preflight(
            [_incoming(version=4)],
            [_existing(version=1), _existing(version=3)],
        )


def test_corrupt_existing_prev_pointer_fails_closed_before_row_classification():
    with pytest.raises(ValueError, match="prevVersionId mismatch"):
        _preflight().course_catalog_preflight(
            [_incoming(version=3)],
            [_existing(version=1), _existing(version=2, prev_version_id=999999)],
        )


def test_corrupt_existing_v1_with_predecessor_fails_closed():
    with pytest.raises(ValueError, match="v1 prevVersionId"):
        _preflight().course_catalog_preflight(
            [_incoming(version=2)],
            [_existing(version=1, prev_version_id=12345)],
        )


def test_corrupt_existing_snapshot_missing_course_id_fails_closed():
    broken = _existing()
    broken["courseId"] = None
    with pytest.raises(ValueError, match="missing/invalid courseId"):
        _preflight().course_catalog_preflight([_incoming()], [broken])
