"""Browser-only auth transport.

PC surfaces keep access tokens in memory only and rotate refresh tokens through HttpOnly cookies.
Staff PC, platform control-plane PC and student PC use independent cookie names so opening one
surface in the same browser cannot overwrite or silently refresh into another surface's identity.
Browser login also verifies that the requested surface matches the authenticated account identity.
Miniapp/native clients continue using the existing JSON refresh-token transport because those
runtimes do not share the browser cookie threat model.
"""
from __future__ import annotations

import hashlib
import secrets

import jwt
from fastapi import APIRouter, Depends, Header, Request, Response

from app.api.v1 import auth as auth_api
from app.core.config import settings
from app.core.exceptions import AppException, unauthorized
from app.core.response import fail, success
from app.core.security import create_access_token, decode_token, get_current_user
from app.core.token_store import (
    REFRESH_TTL,
    block_jti,
    consume_refresh,
    consume_refresh_if_matches,
    issue_refresh,
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
_COOKIE_PREFIXES = {
    "staff": "gx_staff_refresh_v2_",
    "platform": "gx_platform_refresh_v2_",
    "student": "gx_student_refresh_v2_",
}


def _normalize_channel(value: str | None) -> str:
    channel = str(value or "").strip().lower()
    if channel not in _COOKIE_NAMES:
        raise unauthorized("浏览器会话通道无效，请重新登录")
    return channel


def _require_browser_session_id(value: str | None) -> str:
    session_id = str(value or "").strip()
    if not session_id or len(session_id) > 256:
        raise unauthorized("浏览器标签页会话无效，请重新登录")
    return session_id


def _browser_session_hash(session_id: str) -> str:
    return hashlib.sha256(_require_browser_session_id(session_id).encode("utf-8")).hexdigest()


def _cookie_name(channel: str, session_id: str) -> str:
    # Never paste caller-controlled header text into a cookie name.
    return f"{_COOKIE_PREFIXES[_normalize_channel(channel)]}{_browser_session_hash(session_id)[:24]}"


def _claims_match_browser_binding(claims: dict, channel: str, session_id: str) -> bool:
    return (
        str(claims.get("browserChannel") or "").strip().lower() == _normalize_channel(channel)
        and str(claims.get("browserSessionIdHash") or "") == _browser_session_hash(session_id)
    )


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


def _decode_signed_token_for_revocation(token: str) -> dict:
    """Verify JWT signature while ignoring only expiry, solely to locate a session for revocation.

    This helper is never used to authorize a request. It exists so an expired access token can still
    identify the browser ``authSessionId`` during logout when another tab has already consumed the
    refresh cookie. Signature/algorithm validation remains mandatory.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
    except jwt.PyJWTError:
        return {}


def _set_refresh_cookie(response: Response, token: str, channel: str, browser_session_id: str) -> None:
    channel = _normalize_channel(channel)
    tab_id = _require_browser_session_id(browser_session_id)
    response.set_cookie(
        key=_cookie_name(channel, tab_id),
        value=token,
        max_age=int(REFRESH_TTL),
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
        path=_COOKIE_PATH,
    )
    # v1 is a shared surface slot: never guess-bind it to a v2 tab.
    for key in (_COOKIE_NAMES[channel], _LEGACY_COOKIE_NAME):
        response.delete_cookie(
            key=key, path=_COOKIE_PATH, httponly=True,
            secure=bool(settings.is_prod), samesite="strict",
        )


def _clear_refresh_cookie(response: Response, channel: str, browser_session_id: str) -> None:
    channel = _normalize_channel(channel)
    tab_id = _require_browser_session_id(browser_session_id)
    for key in (_cookie_name(channel, tab_id), _COOKIE_NAMES[channel], _LEGACY_COOKIE_NAME):
        response.delete_cookie(
            key=key, path=_COOKIE_PATH, httponly=True,
            secure=bool(settings.is_prod), samesite="strict",
        )


def _sessionize_payload(
    payload: dict,
    *,
    browser_channel: str,
    browser_session_id: str,
    session_id: str | None = None,
) -> dict:
    """Bind a newly issued real DB browser credential pair to one concrete tab."""
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
    tab_id = _require_browser_session_id(browser_session_id)
    channel = _normalize_channel(browser_channel)
    sid = str(session_id or claims.get("authSessionId") or secrets.token_urlsafe(24))
    claims["authSessionId"] = sid
    claims["browserChannel"] = channel
    claims["browserSessionIdHash"] = _browser_session_hash(tab_id)
    data["accessToken"] = create_access_token(dict(claims))
    data["refreshToken"] = issue_refresh(dict(claims))
    out = dict(payload)
    out["data"] = data
    return out


def _extract_refresh(
    payload: dict,
    response: Response,
    *,
    expected_channel: str,
    browser_session_id: str,
) -> dict:
    """Move refreshToken into this tab's HttpOnly slot; accessToken remains memory-only."""
    data = dict((payload or {}).get("data") or {})
    refresh_token = str(data.pop("refreshToken", "") or "")
    access_token = str(data.get("accessToken") or "")
    if not refresh_token or not access_token:
        raise unauthorized("刷新令牌签发失败，请重新登录")
    channel = _normalize_channel(expected_channel)
    tab_id = _require_browser_session_id(browser_session_id)
    if _channel_from_access_token(access_token) != channel:
        try:
            consume_refresh(refresh_token)
        except Exception:
            pass
        _clear_refresh_cookie(response, channel, tab_id)
        raise unauthorized("该账号不属于当前登录入口，请使用正确入口重新登录")
    _set_refresh_cookie(response, refresh_token, channel, tab_id)
    out = dict(payload)
    out["data"] = data
    return out


def _rotate_browser_refresh(refresh_token: str, *, channel: str, browser_session_id: str) -> dict:
    """Atomically rotate only a refresh credential bound to this exact browser tab."""
    channel = _normalize_channel(channel)
    tab_id = _require_browser_session_id(browser_session_id)
    claims = consume_refresh_if_matches(
        refresh_token,
        expected_browser_channel=channel,
        expected_browser_session_hash=_browser_session_hash(tab_id),
    )
    if not claims:
        raise unauthorized("浏览器刷新会话无效，请重新登录")
    session_id = str(claims.get("authSessionId") or "")
    if session_id and auth_session_blocked(session_id):
        raise unauthorized("浏览器会话已失效，请重新登录")
    auth_service_db.validate_token_subject(claims)
    claims["authSessionId"] = session_id or secrets.token_urlsafe(24)
    claims["browserChannel"] = channel
    claims["browserSessionIdHash"] = _browser_session_hash(tab_id)
    token = create_access_token(dict(claims))
    new_refresh = issue_refresh(dict(claims))
    audit.record("TOKEN_REFRESH", target_type="auth", target_id=str(claims.get("userId", "-")))
    return success({
        "accessToken": token,
        "refreshToken": new_refresh,
        "tokenType": "Bearer",
        "expiresIn": settings.JWT_EXPIRES_IN,
    }, message="已刷新")


@router.post("/auth/browser-login", summary="浏览器账号密码登录（per-tab HttpOnly refresh Cookie）")
def browser_login(
    body: auth_api.PasswordLoginRequest,
    response: Response,
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    channel = _channel_from_client_type(body.clientType)
    tab_id = _require_browser_session_id(browser_session_id)
    payload = _sessionize_payload(
        auth_api.login(body), browser_channel=channel, browser_session_id=tab_id,
    )
    return _extract_refresh(payload, response, expected_channel=channel, browser_session_id=tab_id)


@router.post("/auth/browser-refresh", summary="浏览器刷新会话（同 surface 多标签页隔离）")
def browser_refresh(
    request: Request,
    response: Response,
    browser_session: str | None = Header(default=None, alias="X-Browser-Session"),
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    channel = _normalize_channel(browser_session)
    tab_id = _require_browser_session_id(browser_session_id)
    refresh_token = request.cookies.get(_cookie_name(channel, tab_id))
    if not refresh_token:
        raise unauthorized("浏览器刷新会话不存在，请重新登录")
    payload = _rotate_browser_refresh(refresh_token, channel=channel, browser_session_id=tab_id)
    return _extract_refresh(payload, response, expected_channel=channel, browser_session_id=tab_id)


@router.post("/auth/browser-switch-role", summary="浏览器切换身份并轮换当前标签页 refreshToken")
def browser_switch_role(
    body: SwitchRoleRequest,
    response: Response,
    user=Depends(get_current_user),
    authorization: str | None = Header(default=None),
    browser_session: str | None = Header(default=None, alias="X-Browser-Session"),
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    channel = _normalize_channel(browser_session)
    tab_id = _require_browser_session_id(browser_session_id)
    raw = (authorization or "")[7:].strip() if (authorization or "").startswith("Bearer ") else (authorization or "").strip()
    access_claims = decode_token(raw) if raw else {}
    if str(user.get("userId") or "").startswith("db-") and not _claims_match_browser_binding(access_claims, channel, tab_id):
        raise unauthorized("浏览器标签页会话不匹配，请重新登录")
    session_id = str(access_claims.get("authSessionId") or "")
    if str(user.get("userId") or "").startswith("db-"):
        result = browser_auth_session_service.switch_role(
            user, body.contextId, body.clientType, auth_session_id=session_id,
        )
        audit.record(
            "切换身份", method="POST", path="/api/v1/auth/browser-switch-role",
            status_code=200, target_type="authz", target_id=body.contextId,
        )
        payload = success(result, message="身份切换成功")
    else:
        payload = auth_api.switch_role(body, user)
    payload = _sessionize_payload(payload, browser_channel=channel, browser_session_id=tab_id)
    return _extract_refresh(payload, response, expected_channel=channel, browser_session_id=tab_id)


def _browser_logout(
    *,
    response: Response,
    channel: str,
    browser_session_id: str,
    refresh_token: str | None,
    authorization: str | None,
):
    """Terminate one browser tab without revoking another tab/device for the same user."""
    channel = _normalize_channel(channel)
    tab_id = _require_browser_session_id(browser_session_id)
    _clear_refresh_cookie(response, channel, tab_id)
    user_ids: set[str] = set()
    try:
        if refresh_token:
            refresh_claims = consume_refresh_if_matches(
                refresh_token,
                expected_browser_channel=channel,
                expected_browser_session_hash=_browser_session_hash(tab_id),
            )
            if not refresh_claims:
                raise unauthorized("浏览器标签页会话不匹配，请重新登录")
            refresh_user = str(refresh_claims.get("userId") or "")
            refresh_session = str(refresh_claims.get("authSessionId") or "")
            if refresh_user:
                user_ids.add(refresh_user)
            if refresh_session:
                block_auth_session(refresh_session)
        raw = (authorization or "")[7:].strip() if (authorization or "").startswith("Bearer ") else (authorization or "").strip()
        if raw:
            try:
                access_claims = decode_token(raw)
            except AppException:
                access_claims = _decode_signed_token_for_revocation(raw)
            if access_claims:
                if str(access_claims.get("userId") or "").startswith("db-") and not _claims_match_browser_binding(access_claims, channel, tab_id):
                    raise unauthorized("浏览器标签页会话不匹配，请重新登录")
                access_user = str(access_claims.get("userId") or "")
                access_session = str(access_claims.get("authSessionId") or "")
                if access_user:
                    user_ids.add(access_user)
                if access_session:
                    block_auth_session(access_session)
                jti = str(access_claims.get("jti") or "")
                if jti:
                    block_jti(jti, float(access_claims.get("exp") or 0) or None)
    except AppException as exc:
        response.status_code = int(exc.http_status)
        return fail(exc.code, exc.message, exc.details)
    audit.record(
        "登出", method="POST", path="/api/v1/auth/browser-logout", status_code=200,
        target_type="auth", target_id=",".join(sorted(user_ids)) or "-",
    )
    return success({"invalidated": True}, message="已登出")


@router.post("/auth/browser-logout", summary="浏览器登出并清除当前标签页 HttpOnly refreshToken")
def browser_logout(
    request: Request,
    response: Response,
    browser_session: str | None = Header(default=None, alias="X-Browser-Session"),
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
    authorization: str | None = Header(default=None),
):
    channel = _normalize_channel(browser_session)
    tab_id = _require_browser_session_id(browser_session_id)
    refresh_token = request.cookies.get(_cookie_name(channel, tab_id))
    return _browser_logout(
        response=response, channel=channel, browser_session_id=tab_id,
        refresh_token=refresh_token, authorization=authorization,
    )
