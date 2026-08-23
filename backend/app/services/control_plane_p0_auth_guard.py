"""Install the control-plane authentication P0 authority bindings.

The repository already uses explicit ``install()`` guards for late-stage
production authority cutovers.  Keeping this cutover additive avoids rewriting
large frozen authentication modules while ensuring every existing caller sees
the same durable functions after route registration.
"""
from __future__ import annotations

_INSTALLED = False
_PASSWORD_LOGIN_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/auth/browser-login",
})
_PASSWORD_LOGIN_SHARED_NAT_LIMIT = 300
_COMPAT_LOGIN_LIMIT = 10
_LOGIN_WINDOW_SECONDS = 60


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.db.session import db_enabled
    from app.core import token_store
    from app.core.context import get_request_meta
    from app.core.exceptions import AppException
    from app.services import auth_challenge_service as captcha
    from app.services import auth_risk_service as risk_store
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
    original_risk_record_failure = risk_store.record_failure

    def use_durable() -> bool:
        return bool(db_enabled() or strict_env())

    def password_aware_login_rate_guard() -> None:
        """Keep password login usable behind shared campus NAT without weakening spray locks.

        Password-bearing login already has durable account, account+IP and IP-only failed-login
        locks in ``control_plane_auth_service``; the IP-only failed-password threshold is wider
        than one account but still fail-closed.  The historical 10 requests/minute *total* IP
        bucket counted successful logins as attacks, so a classroom/campus NAT could deny the
        11th legitimate user.  Give only the two password-login entry paths a higher flood cap;
        mock/wx compatibility endpoints keep the legacy 10/minute ceiling.
        """
        meta = get_request_meta() or {}
        ip = str(meta.get("ip") or "unknown")
        path = str(meta.get("path") or "")
        limit = (
            _PASSWORD_LOGIN_SHARED_NAT_LIMIT
            if path in _PASSWORD_LOGIN_PATHS
            else _COMPAT_LOGIN_LIMIT
        )
        if not p0.rate_limit(f"login:{ip}", limit, _LOGIN_WINDOW_SECONDS):
            raise AppException(
                "RATE_LIMITED",
                "登录过于频繁，请 1 分钟后再试",
                http_status=429,
            )

    def durable_risk_record_failure(
        key: str,
        *,
        threshold: int,
        lock_seconds: int,
        risk_type: str = risk_store.LOGIN_ACCOUNT,
        tenant_id: int | None = None,
    ):
        # LOGIN_IP / PLATFORM_IP describe one network source across the whole
        # relevant authentication plane.  They are deliberately not tenant
        # business data: assigning the last observed tenant would let tenant
        # offboarding delete a cross-tenant password-spray signal.
        if risk_type in {risk_store.LOGIN_IP, risk_store.PLATFORM_IP}:
            tenant_id = None
        return original_risk_record_failure(
            key,
            threshold=threshold,
            lock_seconds=lock_seconds,
            risk_type=risk_type,
            tenant_id=tenant_id,
        )

    # Establish the ownership invariant before any bound compatibility caller
    # can create durable risk rows. control_plane_auth_service keeps a module
    # reference to auth_risk_service, so it sees this binding as well.
    risk_store.record_failure = durable_risk_record_failure

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
    p0.login_rate_guard = password_aware_login_rate_guard

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

    # auth.py imports rate_limit/issue_refresh by value.  Rebind the legacy guard too because
    # browser-login deliberately delegates to auth.login(body) and would otherwise retain the
    # historical 10/minute total-IP cap even after the P0 authority is installed.
    try:
        from app.api.v1 import auth as auth_api
        auth_api.rate_limit = p0.rate_limit
        auth_api.issue_refresh = p0.issue_refresh
        auth_api._login_rate_guard = password_aware_login_rate_guard
    except Exception:
        pass

    try:
        from app.api.v1 import auth_browser
        if hasattr(auth_browser, "issue_refresh"):
            auth_browser.issue_refresh = p0.issue_refresh
    except Exception:
        pass

    _INSTALLED = True
