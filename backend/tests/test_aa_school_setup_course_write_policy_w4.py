"""A-W4 Course import write-projection contracts."""
from __future__ import annotations

import inspect

import pytest


def _policy():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_course_write_policy as policy
    return policy


def _item(*, version=1, code="CS101", **payload_changes):
    payload = {
        "courseCode": code,
        "courseName": "Python程序设计",
        "category": "MAJOR_CORE",
        "nature": "REQUIRED",
        "credit": 3.0,
        "hoursTotal": 48,
        "hoursTheory": 32,
        "hoursPractice": 16,
        "hoursExperiment": None,
        "hoursComputer": None,
        "examMode": "EXAM",
        "ownerCollegeId": 17,
        "ownerTeacherId": 81,
        "isCore": True,
        "prerequisiteCodes": ["MATH101"],
        # These two are deliberately not asserted by course-catalog-v1 and must
        # never overwrite predecessor values even if a caller accidentally
        # leaves them in an intermediate payload.
        "courseNameEn": "SHOULD_NOT_OVERRIDE",
        "description": "SHOULD_NOT_OVERRIDE",
    }
    payload.update(payload_changes)
    return {
        "businessKey": f"{code}@v{version}",
        "courseCode": code,
        "version": version,
        "payload": payload,
    }


def _predecessor(**changes):
    row = {
        "courseId": 9001,
        "courseCode": "CS101",
        "version": 1,
        "status": "ENABLED",
        "courseNameEn": "Python Programming",
        "description": "历史课程简介",
        "applicableMajors": [101, 102],
        "isAllMajor": False,
    }
    row.update(changes)
    return row


def test_write_policy_is_pure_and_owns_no_transaction_or_model_writer():
    source = inspect.getsource(_policy())
    for forbidden in (
        "session()",
        "select(",
        "db.commit",
        "db.flush",
        "AaCourse(",
        "ImportJob(",
        "FileObject(",
    ):
        assert forbidden not in source


def test_new_v1_uses_safe_defaults_for_non_template_fields():
    result = _policy().new_v1_write_projection(_item())
    assert result["courseCode"] == "CS101"
    assert result["version"] == 1
    assert result["prevVersionId"] is None
    assert result["status"] == "DRAFT"
    assert result["payload"]["courseName"] == "Python程序设计"
    assert result["payload"]["courseNameEn"] is None
    assert result["payload"]["description"] is None
    assert result["payload"]["applicableMajors"] == []
    assert result["payload"]["isAllMajor"] is False


def test_successor_inherits_non_template_course_truth_and_only_overlays_template_fields():
    item = _item(
        version=2,
        courseName="Python程序设计（新版）",
        credit=3.5,
        courseNameEn="MALICIOUS_HIDDEN_OVERRIDE",
        description="MALICIOUS_HIDDEN_OVERRIDE",
    )
    result = _policy().successor_write_projection(item, _predecessor())

    assert result["courseCode"] == "CS101"
    assert result["version"] == 2
    assert result["prevVersionId"] == 9001
    assert result["status"] == "DRAFT"
    assert result["payload"]["courseName"] == "Python程序设计（新版）"
    assert result["payload"]["credit"] == 3.5
    assert result["payload"]["courseNameEn"] == "Python Programming"
    assert result["payload"]["description"] == "历史课程简介"
    assert result["payload"]["applicableMajors"] == [101, 102]
    assert result["payload"]["isAllMajor"] is False


def test_successor_copies_all_major_flag_and_does_not_mutate_predecessor_list():
    predecessor = _predecessor(applicableMajors=[201], isAllMajor=True)
    result = _policy().successor_write_projection(_item(version=2), predecessor)
    assert result["payload"]["applicableMajors"] == [201]
    assert result["payload"]["isAllMajor"] is True
    result["payload"]["applicableMajors"].append(202)
    assert predecessor["applicableMajors"] == [201]


@pytest.mark.parametrize(
    ("item", "predecessor", "message"),
    [
        (_item(version=3), _predecessor(version=1), "direct v2"),
        (_item(version=2, code="CS102"), _predecessor(), "courseCode must match"),
        (_item(version=2), _predecessor(status="DRAFT"), "must be ENABLED"),
        (_item(version=2), _predecessor(courseId=None), "predecessor.courseId"),
    ],
)
def test_successor_projection_fails_closed_on_authority_drift(item, predecessor, message):
    with pytest.raises(ValueError, match=message):
        _policy().successor_write_projection(item, predecessor)


def test_new_course_cannot_trust_non_v1_requested_version():
    with pytest.raises(ValueError, match="start at version 1"):
        _policy().new_v1_write_projection(_item(version=2))


def test_contract_exposes_asserted_inherited_and_authority_generated_boundaries():
    contract = _policy().course_import_write_contract()
    assert "courseName" in contract["templateAssertedFields"]
    assert "courseNameEn" not in contract["templateAssertedFields"]
    assert set(contract["successorInheritedFields"]) == {
        "courseNameEn",
        "description",
        "applicableMajors",
        "isAllMajor",
    }
    assert contract["authorityGeneratedFields"] == ["version", "prevVersionId", "status"]
    assert contract["newStatus"] == "DRAFT"
