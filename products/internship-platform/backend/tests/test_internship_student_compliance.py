"""Student-facing compliance must require every current safety course."""
from types import SimpleNamespace

from app.modules.internship.services.internship_student_compliance_service import (
    summarize_required_safety_courses,
)


def course(cid, version="v1", commitment=True, status="ACTIVE"):
    return SimpleNamespace(
        id=cid, title=f"课程{cid}", course_version=version,
        require_commitment=commitment, status=status, is_deleted=False,
    )


def completion(cid, *, version="v1", status="PASSED", passed=True,
               commitment=True, row_id=None):
    return SimpleNamespace(
        id=row_id or cid, course_id=cid, course_version=version,
        status=status, passed=passed, commitment_confirmed=commitment, version=2,
    )


def test_one_passed_course_does_not_complete_three_required_courses():
    result = summarize_required_safety_courses(
        [course(1), course(2), course(3)],
        [completion(1)], required=True)
    assert result["status"] != "VALID"
    assert result["requiredCount"] == 3
    assert result["passedCount"] == 1


def test_all_current_versions_with_commitment_are_valid():
    result = summarize_required_safety_courses(
        [course(1), course(2)],
        [completion(1), completion(2)], required=True)
    assert result["status"] == "VALID"
    assert result["passedCount"] == 2


def test_old_course_version_cannot_satisfy_current_course():
    result = summarize_required_safety_courses(
        [course(1, version="v2")],
        [completion(1, version="v1")], required=True)
    assert result["status"] != "VALID"
    assert result["courses"][0]["currentVersion"] is False
    assert "重新学习" in result["courses"][0]["reason"]


def test_required_commitment_must_be_confirmed():
    result = summarize_required_safety_courses(
        [course(1, commitment=True)],
        [completion(1, commitment=False)], required=True)
    assert result["status"] != "VALID"
    assert "安全承诺" in result["courses"][0]["reason"]


def test_required_rule_without_active_course_is_configuration_error():
    result = summarize_required_safety_courses([], [], required=True)
    assert result["status"] == "CONFIG_ERROR"
    assert "尚未配置" in result["reason"]


def test_optional_safety_rule_is_not_applicable():
    result = summarize_required_safety_courses(
        [course(1)], [], required=False)
    assert result["status"] == "NOT_APPLICABLE"
    assert result["requiredCount"] == 0
