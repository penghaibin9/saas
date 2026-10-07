"""手机号登录专项的安全回归：候选号码绝不能成为认证凭据。"""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("identity", [
    {"loginName": "", "identifierType": "PHONE", "identifier": "13800138000"},
    {"loginName": None, "identifierType": "PHONE", "identifier": "13800138000"},
    {"loginName": "account", "identifierType": None},
    {"identifierType": "phone", "identifier": "13800138000"},
    {"identifierType": "PHONE", "identifier": None},
    {"loginName": "account", "phoneVerified": True},
])
def test_login_dto_rejects_ambiguous_or_untrusted_identity(identity):
    from pydantic import ValidationError
    from app.api.v1.auth import PasswordLoginRequest
    with pytest.raises(ValidationError):
        PasswordLoginRequest(tenantCode="demo", password="not-trimmed ", **identity)


@pytest.mark.parametrize("value", [13800138000, True, None, "138００１３８０００", "138 00138000", "13800138000\n13900139000"])
def test_phone_identifier_rejects_non_ascii_and_non_text(value):
    from app.services.phone_login_service import normalize_login_phone
    with pytest.raises(ValueError):
        normalize_login_phone(value)


def test_existing_building_migration_has_registered_models():
    from app.models import AaClassroom, AaTeachingBuilding
    assert AaTeachingBuilding.__tablename__ == "t_aa_teaching_building"
    assert {"building_id", "floor_no"} <= set(AaClassroom.__table__.columns.keys())


def test_access_context_preserves_credential_epoch(monkeypatch):
    from starlette.requests import Request
    from app.core import security_legacy, token_store
    from app.services import auth_service_db, password_change_gate
    observed = []
    monkeypatch.setattr(security_legacy, "decode_token", lambda _: {"userId": "db-12", "credentialVersion": 9})
    monkeypatch.setattr(token_store, "jti_blocked", lambda _: False)
    monkeypatch.setattr(auth_service_db, "validate_token_subject", lambda ctx: observed.append(ctx.copy()))
    monkeypatch.setattr(password_change_gate, "must_change_password_for_subject", lambda _: False)
    security_legacy.get_current_user(Request({"type": "http", "path": "/api/v1/auth/me", "headers": []}), "Bearer test")
    assert observed[0].get("credentialVersion") == 9


def test_captcha_cannot_cross_identifier_type_or_school():
    from app.services.auth_challenge_service import _subject_hash
    phone = _subject_hash("demo", "13800138000", "PHONE")
    assert phone == _subject_hash("demo", "+8613800138000", "PHONE")
    assert phone != _subject_hash("demo", "13800138000", "ACCOUNT")
    assert phone != _subject_hash("another", "13800138000", "PHONE")


@pytest.mark.parametrize("epoch", [None, 0, 1, True, "2", 2.0])
def test_stale_or_malformed_epoch_rejected_before_cache(monkeypatch, epoch):
    from types import SimpleNamespace
    from app.services import auth_service_db as svc
    from app.core.exceptions import AppException
    monkeypatch.setattr(svc, "db_enabled", lambda: True)
    monkeypatch.setattr(svc, "get_sessionmaker", lambda: lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(svc, "_load_token_user", lambda *_: SimpleNamespace(credential_version=2))
    monkeypatch.setattr(svc, "_subject_cache_matches", lambda _: pytest.fail("Stale epoch reached cache"))
    with pytest.raises(AppException):
        svc.validate_token_subject({"userId": "db-1", "credentialVersion": epoch})


def test_phone_lookup_requires_separate_stable_search_key(monkeypatch):
    from app.core.config import settings
    from app.services.phone_login_service import phone_lookup
    from app.core.exceptions import AppException
    monkeypatch.setattr(settings, "SENSITIVE_SEARCH_HMAC_KEY", "")
    with pytest.raises(AppException):
        phone_lookup(1, "+8613800138000")


def test_committed_epoch_receipt_survives_cache_and_refresh_cleanup_failure(monkeypatch):
    from types import SimpleNamespace
    from app.services import auth_service_db
    def unavailable(*args, **kwargs):
        raise RuntimeError("sensitive diagnostic must not escape")
    monkeypatch.setattr(auth_service_db, "invalidate_subject_cache", unavailable)
    monkeypatch.setattr("app.core.token_store.revoke_refresh_by_user", unavailable)
    receipt = auth_service_db.credential_change_receipt(SimpleNamespace(id=1, tenant_id=1, credential_version=7), {})
    assert receipt['success'] and receipt['runtimeMaterialized'] and receipt['credentialVersion'] == 7
    assert receipt['cacheRecoveryRequired'] and receipt['refreshCleanupRequired']
    assert 'sensitive diagnostic' not in str(receipt)


def test_pending_or_contact_phone_cannot_be_normalized_as_login_identifier():
    from app.services.phone_login_service import normalize_login_phone

    assert normalize_login_phone(" 13800138000 ") == "+8613800138000"
    with pytest.raises(ValueError):
        normalize_login_phone("138****8000")
    with pytest.raises(ValueError):
        normalize_login_phone("13800138000/13900139000")


def test_browser_login_uses_typed_control_plane_authority_not_legacy_service(monkeypatch):
    """The browser wrapper calls auth.login, so this guards both ACCOUNT and PHONE wiring."""
    from app.api.v1 import auth
    from app.services import control_plane_auth_service

    seen = {}
    monkeypatch.setattr(auth.captcha_svc, "enforce_login_captcha", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth.audit, "record", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        auth.auth_service_db, "login_with_password",
        lambda *args, **kwargs: pytest.fail("browser login must not call the untyped legacy authority"),
    )
    monkeypatch.setattr(
        control_plane_auth_service, "login_with_password",
        lambda identifier, password, tenant, client, *, identifier_type: seen.update({
            "identifier": identifier, "password": password, "tenant": tenant,
            "client": client, "identifier_type": identifier_type,
        }) or {"userId": "db-1"},
    )

    payload = auth.login(auth.PasswordLoginRequest(
        identifierType="PHONE", identifier="13800138000", password="safe-test-password",
        tenantCode="school-a", clientType="PC",
    ))

    assert payload["data"]["userId"] == "db-1"
    assert seen == {
        "identifier": "+8613800138000", "password": "safe-test-password",
        "tenant": "school-a", "client": "PC", "identifier_type": "PHONE",
    }
