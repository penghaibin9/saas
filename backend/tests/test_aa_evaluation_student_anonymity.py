"""学生评教匿名、名单归属与单人单次提交合同。"""
from types import SimpleNamespace

import pytest


def test_anonymous_token_is_deterministic_but_not_plain_identity(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    monkeypatch.setattr(service, "_tid", lambda: 88)
    first = service._submission_token(12, 345)
    second = service._submission_token(12, 345)
    other = service._submission_token(12, 346)

    assert first == second
    assert first != other
    assert "345" not in first
    assert len(first) == 64


def test_anonymous_token_does_not_change_when_jwt_secret_rotates(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    monkeypatch.setattr(service, "_tid", lambda: 88)
    monkeypatch.setattr(service.settings, "FIELD_ENCRYPTION_KEY", "stable-anonymous-data-key")
    monkeypatch.setattr(service.settings, "JWT_SECRET", "jwt-secret-before")
    before = service._submission_token(12, 345)
    monkeypatch.setattr(service.settings, "JWT_SECRET", "jwt-secret-after")
    after = service._submission_token(12, 345)

    assert before == after


def test_missing_anonymous_token_key_fails_closed(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    monkeypatch.setattr(service.settings, "FIELD_ENCRYPTION_KEY", "")
    with pytest.raises(AppException) as exc:
        service._anonymous_token_key()

    assert exc.value.http_status == 500
    assert "凭证密钥未配置" in exc.value.message


def test_reserved_anonymous_token_cannot_be_overridden_by_client():
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    encoded = service._encode_student_answers(
        {"q1": 95, service._RESERVED_TOKEN_KEY: "client-forged"},
        "server-signed",
    )

    assert '"q1":95' in encoded
    assert f'"{service._RESERVED_TOKEN_KEY}":"server-signed"' in encoded
    assert "client-forged" not in encoded


def test_non_student_cannot_submit_student_evaluation():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    task = SimpleNamespace(id=1, teaching_task_id=2)
    with pytest.raises(AppException) as exc:
        service._student_submission_context(
            object(),
            {"userType": "STAFF", "currentRoleCode": "ACADEMIC_TEACHER"},
            task,
        )

    assert exc.value.http_status == 403


def test_student_must_belong_to_current_official_roster(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service
    from app.modules.academic_affairs.services import academic_affairs_roster_consumer_service as roster_service
    from app.services import mobile_student_identity_facade

    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(
        mobile_student_identity_facade,
        "resolve_student",
        lambda _db, _user: SimpleNamespace(id=7),
    )
    monkeypatch.setattr(
        roster_service,
        "resolve_versioned_roster",
        lambda _db, _task_id: {"studentIds": [8, 9], "memberCount": 2},
    )

    with pytest.raises(AppException) as exc:
        service._student_submission_context(
            object(),
            {"userType": "STUDENT", "currentRoleCode": "STUDENT"},
            SimpleNamespace(id=3, teaching_task_id=4),
        )

    assert exc.value.http_status == 403
    assert "不在该课程正式教学班名单" in exc.value.message


def test_valid_student_gets_only_pseudonymous_submission_context(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service
    from app.modules.academic_affairs.services import academic_affairs_roster_consumer_service as roster_service
    from app.services import mobile_student_identity_facade

    profile = SimpleNamespace(id=7, student_no="S0007", real_name="张三")
    roster = {"studentIds": [7, 8], "memberCount": 2, "rosterVersionId": "10"}
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(mobile_student_identity_facade, "resolve_student", lambda _db, _user: profile)
    monkeypatch.setattr(roster_service, "resolve_versioned_roster", lambda _db, _task_id: roster)

    resolved_profile, resolved_roster, token = service._student_submission_context(
        object(),
        {"userType": "STUDENT", "currentRoleCode": "STUDENT"},
        SimpleNamespace(id=3, teaching_task_id=4),
    )

    assert resolved_profile is profile
    assert resolved_roster is roster
    assert len(token) == 64
    assert profile.student_no not in token
    assert profile.real_name not in token


def test_student_audit_never_uses_current_account_operator():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_evaluation_public_service.py"
    ).read_text(encoding="utf-8")

    assert 'operator="ANONYMOUS_STUDENT"' in source
    assert 'detail="学生匿名评教提交"' in source
    assert "query.with_for_update()" in source
    assert "answers_json.like(_token_pattern(" in source
    assert "settings.JWT_SECRET.encode" not in source
    assert "settings.FIELD_ENCRYPTION_KEY" in source
