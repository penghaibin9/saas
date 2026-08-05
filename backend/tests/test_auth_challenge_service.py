from __future__ import annotations

import base64

import pytest

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.token_store import record_login_failure, reset_all_for_tests
from app.services import auth_challenge_service as svc


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "local")
    monkeypatch.setattr(settings, "REDIS_URL", "")
    reset_all_for_tests()
    svc.reset_for_tests()
    yield
    reset_all_for_tests()
    svc.reset_for_tests()


def test_captcha_is_raster_png_single_use():
    data = svc.issue_captcha(svc.PASSWORD_LOGIN, "school", "teacher", "nonce", "PC")
    raw = base64.b64decode(data["imageDataUrl"].split(",", 1)[1])
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    svc.verify_captcha(data["captchaId"], data["devCode"], svc.PASSWORD_LOGIN, "school", "teacher", "nonce", "PC")
    with pytest.raises(AppException) as replay:
        svc.verify_captcha(data["captchaId"], data["devCode"], svc.PASSWORD_LOGIN, "school", "teacher", "nonce", "PC")
    assert replay.value.code == "CAPTCHA_EXPIRED"


def test_wrong_code_consumes_challenge():
    data = svc.issue_captcha(svc.WX_BIND, "school", "student", "nonce", "STUDENT_MINI")
    with pytest.raises(AppException) as wrong:
        svc.verify_captcha(data["captchaId"], "000000", svc.WX_BIND, "school", "student", "nonce", "STUDENT_MINI")
    assert wrong.value.code == "CAPTCHA_INVALID"
    with pytest.raises(AppException):
        svc.verify_captcha(data["captchaId"], data["devCode"], svc.WX_BIND, "school", "student", "nonce", "STUDENT_MINI")


def test_platform_always_requires_captcha():
    with pytest.raises(AppException) as exc:
        svc.enforce_login_captcha(svc.PLATFORM_LOGIN, "platform", "owner", None, None, "n")
    assert exc.value.code == "CAPTCHA_REQUIRED"


def test_regular_login_becomes_adaptive_after_two_failures():
    key = svc.login_guard_key("school", "teacher")
    assert not svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")
    record_login_failure(key, threshold=5, lock_seconds=900)
    assert not svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")
    record_login_failure(key, threshold=5, lock_seconds=900)
    assert svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")


def test_guard_key_does_not_contain_account_plaintext():
    key = svc.login_guard_key("school-code", "teacher@example.com")
    assert "school-code" not in key
    assert "teacher@example.com" not in key


def test_captcha_is_bound_to_client_type():
    data = svc.issue_captcha(svc.PASSWORD_LOGIN, "school", "teacher", "nonce", "PC")
    with pytest.raises(AppException) as exc:
        svc.verify_captcha(
            data["captchaId"], data["devCode"], svc.PASSWORD_LOGIN,
            "school", "teacher", "nonce", "TEACHER_MINI",
        )
    assert exc.value.code == "CAPTCHA_INVALID"


def test_captcha_issue_requires_complete_binding():
    cases = [
        {"login_name": "", "client_nonce": "nonce", "client_type": "PC"},
        {"login_name": "teacher", "client_nonce": "", "client_type": "PC"},
        {"login_name": "teacher", "client_nonce": "nonce", "client_type": ""},
    ]
    for case in cases:
        with pytest.raises(AppException) as exc:
            svc.issue_captcha(svc.PASSWORD_LOGIN, "school", **case)
        assert exc.value.code == "VALIDATION_ERROR"


def test_captcha_scene_rejects_wrong_client_type():
    with pytest.raises(AppException) as platform_exc:
        svc.issue_captcha(svc.PLATFORM_LOGIN, "platform", "owner", "nonce", "PC")
    assert platform_exc.value.code == "VALIDATION_ERROR"

    with pytest.raises(AppException) as bind_exc:
        svc.issue_captcha(svc.WX_BIND, "school", "student", "nonce", "PLATFORM_PC")
    assert bind_exc.value.code == "VALIDATION_ERROR"


def test_wx_bind_request_preserves_and_accepts_client_type():
    from app.api.v1.auth import WxBindRequest

    body = WxBindRequest(
        wxToken="wx-token-long-enough",
        tenantCode="school",
        loginName="teacher",
        password="secret",
        clientType="TEACHER_MINI",
        clientNonce="nonce",
    )
    assert body.clientType == "TEACHER_MINI"

    data = svc.issue_captcha(
        svc.WX_BIND, body.tenantCode, body.loginName,
        body.clientNonce, body.clientType,
    )
    svc.verify_captcha(
        data["captchaId"], data["devCode"], svc.WX_BIND,
        body.tenantCode, body.loginName, body.clientNonce, body.clientType,
    )


def test_dev_code_never_leaks_when_deployment_is_strict(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "production")
    monkeypatch.setattr(svc, "_store", lambda *_args, **_kwargs: None)

    data = svc.issue_captcha(svc.PASSWORD_LOGIN, "school", "teacher", "nonce", "PC")

    assert "devCode" not in data


def test_guardian_verification_sms_login_is_permanently_disabled():
    from app.student_portal.services import guardian_service

    with pytest.raises(AppException) as issue_exc:
        guardian_service.request_otp({"phone": "13800138000"})
    assert issue_exc.value.code == "NO_PERMISSION"

    with pytest.raises(AppException) as consume_exc:
        guardian_service.login({"phone": "13800138000", "code": "123456"})
    assert consume_exc.value.code == "NO_PERMISSION"
    assert "找回密码" in consume_exc.value.message
