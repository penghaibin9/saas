from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.exceptions import AppException
from app.services import auth_challenge_service as svc
from scripts import check_production_redis as redis_preflight


def _strict(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "production")


def test_password_login_risk_gate_rejects_missing_redis_in_production(monkeypatch):
    _strict(monkeypatch)
    monkeypatch.setattr(svc, "get_redis", lambda: None)

    with pytest.raises(AppException) as exc:
        svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")

    assert exc.value.code == "AUTH_STORE_UNAVAILABLE"
    assert exc.value.http_status == 503


def test_password_login_risk_gate_rejects_broken_counter_in_production(monkeypatch):
    _strict(monkeypatch)

    class BrokenCounterRedis:
        def get(self, _key):
            return "not-an-integer"

    monkeypatch.setattr(svc, "get_redis", lambda: BrokenCounterRedis())

    with pytest.raises(AppException) as exc:
        svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")

    assert exc.value.code == "AUTH_STORE_UNAVAILABLE"


def test_password_login_risk_gate_reads_shared_counter_in_production(monkeypatch):
    _strict(monkeypatch)

    class SharedCounterRedis:
        def __init__(self, value: str | None):
            self.value = value

        def get(self, _key):
            return self.value

    monkeypatch.setattr(svc, "get_redis", lambda: SharedCounterRedis("1"))
    assert not svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")

    monkeypatch.setattr(svc, "get_redis", lambda: SharedCounterRedis("2"))
    assert svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")


def test_staging_deployment_mode_is_strict_even_when_app_env_is_development(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "staging")
    monkeypatch.setattr(svc, "get_redis", lambda: None)

    with pytest.raises(AppException) as exc:
        svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")

    assert exc.value.code == "AUTH_STORE_UNAVAILABLE"
    assert exc.value.http_status == 503


def test_redis_preflight_normalizes_prod_and_legacy_env_aliases(monkeypatch):
    for name in ("APP_ENV", "ENV", "ENVIRONMENT"):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("APP_ENV", "prod")
    assert redis_preflight._resolve_app_env() == ("production", None)

    monkeypatch.delenv("APP_ENV")
    monkeypatch.setenv("ENV", "stage")
    assert redis_preflight._resolve_app_env() == ("staging", None)


def test_redis_preflight_rejects_conflicting_environment_aliases(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    resolved, error = redis_preflight._resolve_app_env()

    assert resolved == ""
    assert error and "冲突" in error


def test_redis_preflight_treats_prod_deployment_alias_as_strict(monkeypatch):
    for name in ("APP_ENV", "ENV", "ENVIRONMENT", "REDIS_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEPLOYMENT_MODE", "prod")

    assert redis_preflight.main() == 1
