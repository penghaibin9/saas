"""鉴权上下文必须保留学生稳定身份键，防止学号更正后四端教务服务解析漂移。"""
from __future__ import annotations


def test_get_current_user_preserves_student_id(monkeypatch):
    from app.core import security
    from app.core import token_store
    from app.services import auth_service_db

    claims = {
        "userId": "db-42",
        "loginName": "20260001",
        "realName": "测试学生",
        "userType": "STUDENT",
        "tenantId": "7",
        "studentId": "9001",
        "studentNo": "20260001",
        "activeContextId": "role:8",
        "currentRoleCode": "STUDENT",
        "permissionVersion": "u1|STUDENT:1",
        "jti": "jti-test",
        "exp": 4102444800,
    }

    monkeypatch.setattr(security, "decode_token", lambda token: dict(claims))
    monkeypatch.setattr(token_store, "jti_blocked", lambda jti: False)
    monkeypatch.setattr(token_store, "rate_limit", lambda *args, **kwargs: True)

    seen = {}

    def validate(ctx):
        seen.update(ctx)
        return ctx

    monkeypatch.setattr(auth_service_db, "validate_token_subject", validate)

    user = security.get_current_user("Bearer fake-token")

    assert user["studentId"] == "9001"
    assert user["studentNo"] == "20260001"
    assert seen["studentId"] == "9001"


def test_get_current_user_does_not_invent_student_id(monkeypatch):
    from app.core import security
    from app.core import token_store

    claims = {
        "userId": "mock-teacher",
        "loginName": "teacher",
        "realName": "测试教师",
        "userType": "TEACHER",
        "tenantId": "7",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "jti": "jti-teacher",
        "exp": 4102444800,
    }
    monkeypatch.setattr(security, "decode_token", lambda token: dict(claims))
    monkeypatch.setattr(token_store, "jti_blocked", lambda jti: False)
    monkeypatch.setattr(token_store, "rate_limit", lambda *args, **kwargs: True)

    user = security.get_current_user("Bearer fake-token")

    assert user["studentId"] is None
    assert user["userType"] == "TEACHER"
