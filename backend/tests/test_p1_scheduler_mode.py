"""P1：SCHEDULER_MODE 与多 worker 守卫。"""
from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.security import assert_scheduler_safe


def test_multi_worker_web_scheduler_rejected(monkeypatch):
    s = Settings(APP_ENV="development", DEPLOYMENT_MODE="local",
                 SCHEDULER_MODE="web", WEB_CONCURRENCY=2, MULTI_INSTANCE=False)
    monkeypatch.setattr("app.core.security.settings", s)
    with pytest.raises(RuntimeError, match="SCHEDULER_MODE"):
        assert_scheduler_safe()


def test_multi_instance_web_scheduler_rejected(monkeypatch):
    s = Settings(APP_ENV="development", DEPLOYMENT_MODE="local",
                 SCHEDULER_MODE="web", WEB_CONCURRENCY=1, MULTI_INSTANCE=True)
    monkeypatch.setattr("app.core.security.settings", s)
    with pytest.raises(RuntimeError, match="SCHEDULER_MODE"):
        assert_scheduler_safe()


def test_external_mode_ok_with_multi(monkeypatch):
    s = Settings(APP_ENV="production", DEPLOYMENT_MODE="production",
                 SCHEDULER_MODE="external", WEB_CONCURRENCY=4, MULTI_INSTANCE=True,
                 DEBUG=False, DB_ENABLED=True, MOCK_LOGIN_ENABLED="false",
                 JWT_SECRET="prod-secret-key-32chars-minimum!!",
                 CORS_ORIGINS="https://a.example", INTERNAL_OPS_TOKEN="ops",
                 DATABASE_URL="mysql+pymysql://u:p@127.0.0.1:3306/db")
    assert s.SCHEDULER_MODE == "external"
    monkeypatch.setattr("app.core.security.settings", s)
    assert_scheduler_safe()


def test_dev_single_web_ok(monkeypatch):
    s = Settings(APP_ENV="development", DEPLOYMENT_MODE="local",
                 SCHEDULER_MODE="web", WEB_CONCURRENCY=1, MULTI_INSTANCE=False)
    monkeypatch.setattr("app.core.security.settings", s)
    assert_scheduler_safe()


def test_production_defaults_scheduler_external():
    s = Settings(APP_ENV="production", DEPLOYMENT_MODE="production",
                 DEBUG=False, DB_ENABLED=True, MOCK_LOGIN_ENABLED="false",
                 JWT_SECRET="prod-secret-key-32chars-minimum!!",
                 CORS_ORIGINS="https://a.example", INTERNAL_OPS_TOKEN="ops",
                 DATABASE_URL="mysql+pymysql://u:p@127.0.0.1:3306/db")
    assert s.SCHEDULER_MODE == "external"
