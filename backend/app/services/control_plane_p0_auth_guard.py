"""Install the control-plane authentication P0 authority bindings.

The repository already uses explicit ``install()`` guards for late-stage
production authority cutovers.  Keeping this cutover additive avoids rewriting
large frozen authentication modules while ensuring every existing caller sees
the same durable functions after route registration.
"""
from __future__ import annotations

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.db.session import db_enabled
    from app.core import token_store
    from app.services import auth_challenge_service as captcha
    from app.services import auth_service_db
    from app.services import control_plane_auth_service as p0
    from app.services import wx_auth_service
    from app.services.auth_risk_service import strict_env

    original_login_locked = token_store.login_locked
    original_record_failure = token_store.record_login_failure
    original_failure_count = token_store.get_login_failure_count
    original_reset_failure = token_store.reset_login_failures
    original_captcha_store = captcha._store
    original_captcha_consume = captcha._consume
    original_captcha_required = captcha.captcha_required

    def use_durable() -> bool:
        return bool(db_enabled() or strict_env())

    def login_locked(key: str) -> int:
        return p0.login_locked_compat(key) if use_durable() else original_login_locked(key)

    def record_failure(key: str, threshold: int | None = None,
                       lock_seconds: int | None = None):
        if use_durable():
            return p0.record_login_failure_compat(key, threshold, lock_seconds)
        return original_record_failure(key, threshold, lock_seconds)

    def failure_count(key: str) -> int:
        return p0.failure_count_compat(key) if use_durable() else original_failure_count(key)

    def reset_failure(key: str) -> None:
        if use_durable():
            p0.reset_login_failures_compat(key)
        else:
            original_reset_failure(key)

    def challenge_store(captcha_id: str, payload: dict, ttl: int) -> None:
        if use_durable():
            p0.store_challenge(captcha_id, payload, ttl)
        else:
            original_captcha_store(captcha_id, payload, ttl)

    def challenge_consume(captcha_id: str):
        if use_durable():
            return p0.consume_challenge(captcha_id)
        return original_captcha_consume(captcha_id)

    def adaptive_captcha_required(scene: str, tenant_code: str | None, login_name: str | None) -> bool:
        if use_durable():
            return p0.captcha_required(scene, tenant_code, login_name)
        return original_captcha_required(scene, tenant_code, login_name)

    # Canonical compatibility facade.
    token_store.login_locked = login_locked
    token_store.record_login_failure = record_failure
    token_store.get_login_failure_count = failure_count
    token_store.reset_login_failures = reset_failure
    token_store.rate_limit = p0.rate_limit

    # Modules that imported the old functions by value need their module globals
    # rebound as well; otherwise a route could silently bypass the new authority.
    auth_service_db.login_locked = login_locked
    auth_service_db.record_login_failure = record_failure
    auth_service_db.reset_login_failures = reset_failure
    auth_service_db.login_with_password = p0.login_with_password
    auth_service_db.change_own_password = p0.change_own_password
    auth_service_db._login_result = p0._login_result

    captcha.get_login_failure_count = failure_count
    captcha.rate_limit = p0.rate_limit
    captcha._strict_login_failure_count = failure_count
    captcha._store = challenge_store
    captcha._consume = challenge_consume
    captcha.captcha_required = adaptive_captcha_required

    wx_auth_service.login_locked = login_locked
    wx_auth_service.record_login_failure = record_failure
    wx_auth_service.reset_login_failures = reset_failure
    wx_auth_service.build_login_result = p0.build_login_result
    wx_auth_service.wx_bind = p0.wx_bind

    # auth.py imports rate_limit/issue_refresh by value.  Some non-replaced
    # compatibility endpoints (mock/wx login) still call its _login_rate_guard.
    try:
        from app.api.v1 import auth as auth_api
        auth_api.rate_limit = p0.rate_limit
        auth_api.issue_refresh = p0.issue_refresh
    except Exception:
        pass

    try:
        from app.api.v1 import auth_browser
        if hasattr(auth_browser, "issue_refresh"):
            auth_browser.issue_refresh = p0.issue_refresh
    except Exception:
        pass

    _INSTALLED = True
