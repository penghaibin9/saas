"""P0 移动身份与班级范围止血回归。"""
from __future__ import annotations

import pytest
from starlette.requests import Request

from app.core.context import set_current_user
from app.core.exceptions import AppException
from app.core.security import _optional_positive_int_claim
from app.middleware.context import _mobile_teacher_identity_deny
from app.services import mobile_teacher_service as svc


@pytest.mark.parametrize("user_type", ["STUDENT", "GUARDIAN", "", None, "UNKNOWN", "PLATFORM_SUPER_ADMIN"])
def test_mobile_teacher_rejects_non_school_staff(user_type):
    with pytest.raises(AppException):
        svc._require_teacher({"userId": "u-1", "userType": user_type})


@pytest.mark.parametrize("user_type", ["TEACHER", "STAFF", "ADMIN", "SCHOOL_ADMIN"])
def test_mobile_teacher_accepts_explicit_school_staff(user_type):
    user = {"userId": "u-1", "userType": user_type}
    assert svc._require_teacher(user) is user


def test_student_id_claim_is_stable_and_fail_closed():
    assert _optional_positive_int_claim({"studentId": "123"}, "studentId") == 123
    assert _optional_positive_int_claim({}, "studentId") is None
    for raw in (0, -1, "bad"):
        with pytest.raises(Exception):
            _optional_positive_int_claim({"studentId": raw}, "studentId")


def test_security_auditor_is_not_business_tenant_admin(monkeypatch):
    monkeypatch.setattr(svc._impl, "db_enabled", lambda: False)
    monkeypatch.setattr(svc._impl, "_tid", lambda: 1001)
    scope = svc.resolve_teacher_scope({
        "userId": "db-7",
        "userType": "STAFF",
        "currentRoleCode": "SECURITY_AUDITOR",
        "realName": "审计员",
    })
    assert scope["mode"] == "SCOPED"
    assert scope["by"] == "DEFAULT_DENY"


def test_requested_class_must_be_inside_teacher_allowed_set():
    assert svc._authorize_requested_class("SCOPED", 10, {10, 11}) == 10
    assert svc._authorize_requested_class("SCOPED", None, {10, 11}) is None
    with pytest.raises(AppException):
        svc._authorize_requested_class("SCOPED", 99, {10, 11})
    assert svc._authorize_requested_class("ADMIN_TENANT", 99, set()) == 99


@pytest.mark.parametrize("raw", ["x", "0", -1, object()])
def test_invalid_class_id_returns_validation_error(raw):
    with pytest.raises(AppException):
        svc._parse_class_id(raw)


def test_aggregate_failure_is_visible_not_fake_zero():
    def broken(*_args, **_kwargs):
        raise RuntimeError("db down")

    with pytest.raises(AppException) as exc:
        svc._safe_list(broken, 1, 20)
    assert getattr(exc.value, "code", None) == "METRIC_UNAVAILABLE"


def _request(path: str) -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 443),
    })


def test_middleware_blocks_guardian_from_every_teacher_route():
    set_current_user({"userId": "u-g", "userType": "GUARDIAN"})
    response = _mobile_teacher_identity_deny(_request("/api/v1/mobile/teacher/overview"))
    assert response is not None
    assert response.status_code == 403


def test_middleware_allows_teacher_and_ignores_student_paths():
    set_current_user({"userId": "u-t", "userType": "TEACHER"})
    assert _mobile_teacher_identity_deny(
        _request("/api/v1/mobile/teacher/my-students")) is None
    set_current_user({"userId": "u-s", "userType": "STUDENT"})
    assert _mobile_teacher_identity_deny(
        _request("/api/v1/mobile/student/profile")) is None
