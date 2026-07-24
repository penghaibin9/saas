"""P1：生产配置显式守卫。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.security import assert_prod_flags_safe, assert_scheduler_safe, assert_secret_safe


def test_illegal_app_env_rejected():
    with pytest.raises((ValidationError, ValueError)):
        Settings(APP_ENV="prod-like", DEPLOYMENT_MODE="local")


def test_deployment_production_requires_app_env_production():
    with pytest.raises((ValidationError, ValueError)):
        Settings(APP_ENV="development", DEPLOYMENT_MODE="production",
                 DEBUG=False, DB_ENABLED=True, MOCK_LOGIN_ENABLED="false",
                 JWT_SECRET="x" * 40, CORS_ORIGINS="https://a.example",
                 INTERNAL_OPS_TOKEN="ops-token")


def test_production_db_disabled_rejected(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_MODE", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("DB_ENABLED", "false")
    monkeypatch.setenv("MOCK_LOGIN_ENABLED", "false")
    monkeypatch.setenv("JWT_SECRET", "prod-secret-key-32chars-minimum!!")
    monkeypatch.setenv("CORS_ORIGINS", "https://school.example")
    monkeypatch.setenv("INTERNAL_OPS_TOKEN", "ops")
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://u:p@127.0.0.1:3306/db")
    get_settings.cache_clear()
    s = Settings(
        APP_ENV="production", DEPLOYMENT_MODE="production", DEBUG=False,
        DB_ENABLED=False, MOCK_LOGIN_ENABLED="false",
        JWT_SECRET="prod-secret-key-32chars-minimum!!",
        CORS_ORIGINS="https://school.example",
        INTERNAL_OPS_TOKEN="ops",
        DATABASE_URL="mysql+pymysql://u:p@127.0.0.1:3306/db",
    )
    monkeypatch.setattr("app.core.security.settings", s)
    with pytest.raises(RuntimeError, match="DB_ENABLED"):
        assert_prod_flags_safe()


def test_production_mock_login_rejected(monkeypatch):
    s = Settings(
        APP_ENV="production", DEPLOYMENT_MODE="production", DEBUG=False,
        DB_ENABLED=True, MOCK_LOGIN_ENABLED="true",
        JWT_SECRET="prod-secret-key-32chars-minimum!!",
        CORS_ORIGINS="https://school.example",
        INTERNAL_OPS_TOKEN="ops",
        DATABASE_URL="mysql+pymysql://u:p@127.0.0.1:3306/db",
    )
    monkeypatch.setattr("app.core.security.settings", s)
    with pytest.raises(RuntimeError, match="MOCK_LOGIN"):
        assert_prod_flags_safe()


def test_development_allows_dev_defaults():
    s = Settings(APP_ENV="development", DEPLOYMENT_MODE="local")
    assert s.is_prod is False
    assert s.mock_login_enabled is True
    # 不抛
    from app.core import security as sec
    old = sec.settings
    try:
        sec.settings = s
        assert_secret_safe()
        assert_prod_flags_safe()
        assert_scheduler_safe()
    finally:
        sec.settings = old


def test_jwt_secret_conflict_rejected():
    with pytest.raises((ValidationError, ValueError)):
        Settings(JWT_SECRET="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                 JWT_SECRET_KEY="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")


def test_env_alias_conflict_rejected():
    with pytest.raises((ValidationError, ValueError)):
        Settings(APP_ENV="development", ENV="production")
