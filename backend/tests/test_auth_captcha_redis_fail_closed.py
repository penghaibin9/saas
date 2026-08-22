from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.exceptions import AppException
from app.services import auth_challenge_service as svc
from app.services import control_plane_auth_service as p0
from scripts import check_production_redis as redis_preflight


def _strict(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "production")


def _durable_captcha_contract(monkeypatch, *, failure_count: int | None) -> None:
    monkeypatch.setattr(p0, "resolve_tenant_id", lambda _tenant_code: 1001)
    monkeypatch.setattr(
        p0,
        "resolve_login_policy",
        lambda **_kwargs: {"captchaAfterFailures": 2},
    )
    monkeypatch.setattr(
        p0.risk,
        "failure_count",
        lambda *_args, **_kwargs: failure_count,
    )


def test_password_login_risk_gate_uses_mysql_authority_when_redis_is_missing(monkeypatch):
    """Redis is only a fast path after P0; durable risk state remains authoritative."""
    _strict(monkeypatch)
    monkeypatch.setattr(svc, "get_redis", lambda: None)
    _durable_captcha_contract(monkeypatch, failure_count=1)

    assert not svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")


def test_password_login_risk_gate_uses_mysql_authority_when_redis_counter_is_broken(monkeypatch):
    _strict(monkeypatch)

    class BrokenCounterRedis:
        def get(self, _key):
            return "not-an-integer"

    monkeypatch.setattr(svc, "get_redis", lambda: BrokenCounterRedis())
    _durable_captcha_contract(monkeypatch, failure_count=2)

    assert svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")


def test_password_login_risk_gate_does_not_trust_legacy_redis_counter(monkeypatch):
    """Changing a legacy Redis counter must not override the durable DB decision."""
    _strict(monkeypatch)

    class SharedCounterRedis:
        def __init__(self, value: str | None):
            self.value = value

        def get(self, _key):
            return self.value

    _durable_captcha_contract(monkeypatch, failure_count=1)

    monkeypatch.setattr(svc, "get_redis", lambda: SharedCounterRedis("1"))
    assert not svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")

    monkeypatch.setattr(svc, "get_redis", lambda: SharedCounterRedis("999"))
    assert not svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")


def test_staging_fails_closed_when_durable_risk_authority_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "staging")
    monkeypatch.setattr(svc, "get_redis", lambda: None)
    _durable_captcha_contract(monkeypatch, failure_count=None)

    with pytest.raises(AppException) as exc:
        svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")

    assert exc.value.code == "AUTH_RISK_STORE_UNAVAILABLE"
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
