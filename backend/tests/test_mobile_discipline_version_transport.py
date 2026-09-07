import pytest

from app.api.v1 import mobile
from app.core.exceptions import AppException
from app.services import _mobile_teacher_service_impl as teacher
from app.services import affairs_discipline_service as discipline


def test_mobile_discipline_route_requires_and_forwards_version(monkeypatch):
    user = {"userType": "TEACHER", "realName": "联调处分老师"}

    with pytest.raises(AppException):
        mobile.teacher_affairs_discipline_review(
            "9007199254740993", body={"action": "APPROVE"}, user=user
        )

    seen = []
    monkeypatch.setattr(
        mobile.tea,
        "affairs_discipline_review",
        lambda actor, case_id, action, reason="", expected_version=None: seen.append(
            (actor, case_id, action, reason, expected_version)
        ) or {"caseId": case_id},
    )
    mobile.teacher_affairs_discipline_review(
        "9007199254740993",
        body={"action": "APPROVE", "reason": "核验通过", "version": 7},
        user=user,
    )
    assert seen == [(user, "9007199254740993", "APPROVE", "核验通过", 7)]


def test_mobile_discipline_remove_forwards_expected_version(monkeypatch):
    user = {"userType": "TEACHER", "realName": "联调处分老师"}
    seen = []
    monkeypatch.setattr(teacher, "_require_teacher", lambda value: value)
    monkeypatch.setattr(teacher, "db_enabled", lambda: True)
    monkeypatch.setattr(discipline, "get_case", lambda case_id, actor: {"status": "REMOVE_REVIEW"})
    monkeypatch.setattr(
        discipline,
        "review_remove",
        lambda case_id, actor, action, reason="", expected_version=None: seen.append(
            (case_id, actor, action, reason, expected_version)
        ) or {"caseId": case_id},
    )
    monkeypatch.setattr(teacher, "_audit_write", lambda *args, **kwargs: None)

    teacher.affairs_discipline_review(
        user, "9007199254740993", "APPROVE", "", expected_version=11
    )
    assert seen == [("9007199254740993", user, "APPROVE", "", 11)]
