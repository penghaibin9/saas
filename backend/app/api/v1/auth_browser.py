"""Browser-only auth transport.

PC surfaces keep access tokens in memory only and rotate refresh tokens through HttpOnly cookies.
Staff PC, platform control-plane PC and student PC use independent cookie names so opening one
surface in the same browser cannot overwrite or silently refresh into another surface's identity.
Browser login also verifies that the requested surface matches the authenticated account identity.
Miniapp/native clients continue using the existing JSON refresh-token transport because those
runtimes do not share the browser cookie threat model.
"""
from __future__ import annotations

import secrets
from contextvars import ContextVar

from fastapi import APIRouter, Cookie, Depends, Header, Response

from app.api.v1 import auth as auth_api
from app.core.config import settings
from app.core.exceptions import AppException, unauthorized
from app.core.response import fail, success
from app.core.security import create_access_token, decode_token, get_current_user
from app.core.token_store import (
    REFRESH_TTL,
    block_jti,
    consume_refresh,
    issue_refresh,
    revoke_refresh_by_session,
)
from app.schemas.auth import SwitchRoleRequest
from app.services import auth_service_db
from app.services import browser_auth_session_service
from app.services import mock_audit_service as audit
from app.services.browser_auth_session_blocklist import auth_session_blocked, block_auth_session

router = APIRouter()

_COOKIE_PATH = "/api/v1/auth"
_LEGACY_COOKIE_NAME = "gx_refresh_v1"
_COOKIE_NAMES = {
    "staff": "gx_staff_refresh_v1",
    "platform": "gx_platform_refresh_v1",
    "student": "gx_student_refresh_v1",
}
_BROWSER_REVOKE_SESSION = ContextVar("browser_revoke_session", default="")


def _normalize_channel(value: str | None) -> str:
    channel = str(value or "").strip().lower()
    if channel not in _COOKIE_NAMES:
        raise unauthorized("浏览器会话通道无效，请重新登录")
    return channel


def _channel_from_client_type(client_type: str | None) -> str:
    value = str(client_type or "PC").strip().upper()
    if value == "PLATFORM_PC":
        return "platform"
    if value == "STUDENT_PC":
        return "student"
    return "staff"


def _channel_from_access_token(token: str) -> str:
    """Derive the durable browser surface from authenticated identity, not caller-supplied clientType.

    ``clientType`` is a request hint and is therefore not allowed to turn a teacher into a student
    surface (or vice versa). Platform/student account identity wins; only identity-neutral legacy
    tokens fall back to their clientType.
    """
    claims = decode_token(token)
    client_type = str(claims.get("clientType") or "").strip().upper()
    user_type = str(claims.get("userType") or "").strip().upper()
    role = str(claims.get("currentRoleCode") or "").strip().upper()
    if user_type.startswith("PLATFORM_") or role == "PLATFORM_SUPER_ADMIN":
        return "platform"
    if user_type == "STUDENT" or role == "STUDENT":
        return "student"
    if user_type or role:
        return "staff"
    return _channel_from_client_type(client_type)


def _set_refresh_cookie(response: Response, token: str, channel: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAMES[_normalize_channel(channel)],
        value=token,
        max_age=int(REFRESH_TTL),
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
        path=_COOKIE_PATH,
    )
    response.delete_cookie(
        key=_LEGACY_COOKIE_NAME,
        path=_COOKIE_PATH,
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response, channel: str) -> None:
    response.delete_cookie(
        key=_COOKIE_NAMES[_normalize_channel(channel)],
        path=_COOKIE_PATH,
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
    )
    response.delete_cookie(
        key=_LEGACY_COOKIE_NAME,
        path=_COOKIE_PATH,
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
    )


def _sessionize_payload(payload: dict, *, session_id: str | None = None) -> dict:
    """Replace a just-issued real DB auth pair with one browser-session-scoped pair.

    Test stubs, mock identities and other non-DB tokens keep the historical path. For a real DB
    login/switch, the original refresh is consumed before replacement so no unsessionized durable
    credential is left behind. The discarded access token was never exposed to the browser.
    """
    data = dict((payload or {}).get("data") or {})
    refresh_token = str(data.get("refreshToken") or "")
    access_token = str(data.get("accessToken") or "")
    if not refresh_token or not access_token:
        raise unauthorized("刷新令牌签发失败，请重新登录")
    try:
        access_claims = decode_token(access_token)
    except AppException:
        return payload
    if not str(access_claims.get("userId") or "").startswith("db-"):
        return payload

    claims = consume_refresh(refresh_token)
    if not claims:
        raise unauthorized("刷新令牌签发失败，请重新登录")
    sid = str(session_id or claims.get("authSessionId") or secrets.token_urlsafe(24))
    claims["authSessionId"] = sid
    data["accessToken"] = create_access_token(dict(claims))
    data["refreshToken"] = issue_refresh(dict(claims))
    out = dict(payload)
    out["data"] = data
    return out


def _extract_refresh(payload: dict, response: Response, *, expected_channel: str | None = None) -> dict:
    """Move refreshToken from JSON into the correct HttpOnly cookie; accessToken remains visible."""
    data = dict((payload or {}).get("data") or {})
    refresh_token = str(data.pop("refreshToken", "") or "")
    access_token = str(data.get("accessToken") or "")
    if not refresh_token or not access_token:
        raise unauthorized("刷新令牌签发失败，请重新登录")
    actual_channel = _channel_from_access_token(access_token)
    if expected_channel is not None and actual_channel != _normalize_channel(expected_channel):
        try:
            consume_refresh(refresh_token)
        except Exception:
            pass
        _clear_refresh_cookie(response, expected_channel)
        raise unauthorized("该账号不属于当前登录入口，请使用正确入口重新登录")
    _set_refresh_cookie(response, refresh_token, actual_channel)
    out = dict(payload)
    out["data"] = data
    return out


def _cookie_for_channel(channel: str, *, staff: str | None, platform: str | None, student: str | None) -> str | None:
    return {
        "staff": staff,
        "platform": platform,
        "student": student,
    }[_normalize_channel(channel)]


def _rotate_browser_refresh(refresh_token: str) -> dict:
    """Rotate one browser cookie and opportunistically upgrade legacy pre-session cookies."""
    claims = consume_refresh(refresh_token)
    if not claims:
        raise unauthorized("refreshToken 无效或已使用，请重新登录")
    session_id = str(claims.get("authSessionId") or "")
    if session_id and auth_session_blocked(session_id):
        raise unauthorized("浏览器会话已失效，请重新登录")
    auth_service_db.validate_token_subject(claims)
    claims["authSessionId"] = session_id or secrets.token_urlsafe(24)
    token = create_access_token(dict(claims))
    new_refresh = issue_refresh(dict(claims))
    audit.record("TOKEN_REFRESH", target_type="auth", target_id=str(claims.get("userId", "-")))
    return success(
        {
            "accessToken": token,
            "refreshToken": new_refresh,
            "tokenType": "Bearer",
            "expiresIn": settings.JWT_EXPIRES_IN,
        },
        message="已刷新",
    )


@router.post("/auth/browser-login", summary="浏览器账号密码登录（入口身份匹配 + 独立 HttpOnly refresh Cookie）")
def browser_login(body: auth_api.PasswordLoginRequest, response: Response):
    expected_channel = _channel_from_client_type(body.clientType)
    payload = _sessionize_payload(auth_api.login(body))
    return _extract_refresh(payload, response, expected_channel=expected_channel)


@router.post("/auth/browser-refresh", summary="浏览器刷新会话（staff/platform/student 独立 HttpOnly Cookie）")
def browser_refresh(
    response: Response,
    browser_session: str | None = Header(default=None, alias="X-Browser-Session"),
    staff_refresh: str | None = Cookie(default=None, alias=_COOKIE_NAMES["staff"]),
    platform_refresh: str | None = Cookie(default=None, alias=_COOKIE_NAMES["platform"]),
    student_refresh: str | None = Cookie(default=None, alias=_COOKIE_NAMES["student"]),
):
    channel = _normalize_channel(browser_session)
    refresh_token = _cookie_for_channel(
        channel, staff=staff_refresh, platform=platform_refresh, student=student_refresh
    )
    if not refresh_token:
        raise unauthorized("浏览器刷新会话不存在，请重新登录")
    return _extract_refresh(_rotate_browser_refresh(refresh_token), response, expected_channel=channel)


@router.post("/auth/browser-switch-role", summary="浏览器切换身份并轮换对应入口的 HttpOnly refreshToken")
def browser_switch_role(
    body: SwitchRoleRequest,
    response: Response,
    user=Depends(get_current_user),
    authorization: str | None = Header(default=None),
):
    raw = (authorization or "")[7:].strip() if (authorization or "").startswith("Bearer ") else (authorization or "").strip()
    access_claims = decode_token(raw) if raw else {}
    session_id = str(access_claims.get("authSessionId") or "")
    if str(user.get("userId") or "").startswith("db-"):
        result = browser_auth_session_service.switch_role(
            user,
            body.contextId,
            body.clientType,
            auth_session_id=session_id,
        )
        audit.record(
            "切换身份",
            method="POST",
            path="/api/v1/auth/browser-switch-role",
            status_code=200,
            target_type="authz",
            target_id=body.contextId,
        )
        payload = success(result, message="身份切换成功")
    else:
        payload = auth_api.switch_role(body, user)
    # A role switch closes the previous session tombstone and starts a fresh browser session id.
    payload = _sessionize_payload(payload)
    return _extract_refresh(payload, response)


def revoke_refresh_by_user(user_id: str) -> int:
    """Compatibility hook kept for existing browser-logout contracts.

    Despite the historical name, browser logout must never perform a user-wide revoke. It tombstones
    the current authSessionId and removes only refresh siblings in that session. Global revocation
    remains in token_store.revoke_refresh_by_user for password-reset/change and explicit all-device
    security events.
    """
    session_id = str(_BROWSER_REVOKE_SESSION.get() or "")
    if not session_id:
        return 0
    block_auth_session(session_id)
    return revoke_refresh_by_session(user_id, session_id)


def _browser_logout(
    *,
    response: Response,
    channel: str,
    refresh_token: str | None,
    authorization: str | None,
):
    """Terminate one browser-surface session even when its in-memory access token has expired."""
    channel = _normalize_channel(channel)
    _clear_refresh_cookie(response, channel)
    user_ids: set[str] = set()
    session_by_user: dict[str, str] = {}
    try:
        if refresh_token:
            refresh_claims = consume_refresh(refresh_token)
            if refresh_claims:
                refresh_user = str(refresh_claims.get("userId") or "")
                refresh_session = str(refresh_claims.get("authSessionId") or "")
                if refresh_user:
                    user_ids.add(refresh_user)
                    if refresh_session:
                        session_by_user[refresh_user] = refresh_session

        raw = (authorization or "")[7:].strip() if (authorization or "").startswith("Bearer ") else (authorization or "").strip()
        if raw:
            try:
                access_claims = decode_token(raw)
            except AppException:
                access_claims = {}
            if access_claims:
                access_user = str(access_claims.get("userId") or "")
                access_session = str(access_claims.get("authSessionId") or "")
                if access_user:
                    user_ids.add(access_user)
                    if access_session:
                        session_by_user[access_user] = access_session
                jti = str(access_claims.get("jti") or "")
                if jti:
                    block_jti(jti, float(access_claims.get("exp") or 0) or None)

        for user_id in user_ids:
            marker = _BROWSER_REVOKE_SESSION.set(session_by_user.get(user_id, ""))
            try:
                revoke_refresh_by_user(user_id)
            finally:
                _BROWSER_REVOKE_SESSION.reset(marker)
    except AppException as exc:
        response.status_code = int(exc.http_status)
        return fail(exc.code, exc.message, exc.details)

    audit.record(
        "登出",
        method="POST",
        path="/api/v1/auth/browser-logout",
        status_code=200,
        target_type="auth",
        target_id=",".join(sorted(user_ids)) or "-",
    )
    return success({"invalidated": True}, message="已登出")


@router.post("/auth/browser-logout", summary="浏览器登出并清除当前 PC 入口的 HttpOnly refreshToken")
def browser_logout(
    response: Response,
    browser_session: str | None = Header(default=None, alias="X-Browser-Session"),
    staff_refresh: str | None = Cookie(default=None, alias=_COOKIE_NAMES["staff"]),
    platform_refresh: str | None = Cookie(default=None, alias=_COOKIE_NAMES["platform"]),
    student_refresh: str | None = Cookie(default=None, alias=_COOKIE_NAMES["student"]),
    authorization: str | None = Header(default=None),
):
    channel = _normalize_channel(browser_session)
    refresh_token = _cookie_for_channel(
        channel, staff=staff_refresh, platform=platform_refresh, student=student_refresh
    )
    return _browser_logout(
        response=response,
        channel=channel,
        refresh_token=refresh_token,
        authorization=authorization,
    )
