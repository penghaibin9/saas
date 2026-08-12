"""Browser-only auth transport.

PC surfaces keep access tokens in memory only and rotate refresh tokens through HttpOnly cookies.
Staff PC, platform control-plane PC and student PC use independent cookie names so opening one
surface in the same browser cannot overwrite or silently refresh into another surface's identity.
Browser login also verifies that the requested surface matches the authenticated account identity.
Miniapp/native clients continue using the existing JSON refresh-token transport because those
runtimes do not share the browser cookie threat model.
"""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, Response

from app.api.v1 import auth as auth_api
from app.core.config import settings
from app.core.exceptions import AppException, unauthorized
from app.core.response import fail, success
from app.core.security import decode_token, get_current_user
from app.core.token_store import REFRESH_TTL, block_jti, consume_refresh, revoke_refresh_by_user
from app.schemas.auth import SwitchRoleRequest
from app.services import mock_audit_service as audit

router = APIRouter()

_COOKIE_PATH = "/api/v1/auth"
_LEGACY_COOKIE_NAME = "gx_refresh_v1"
_COOKIE_NAMES = {
    "staff": "gx_staff_refresh_v1",
    "platform": "gx_platform_refresh_v1",
    "student": "gx_student_refresh_v1",
}


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


def _extract_refresh(payload: dict, response: Response, *, expected_channel: str | None = None) -> dict:
    """Move refreshToken from JSON into the correct HttpOnly cookie; accessToken remains visible."""
    data = dict((payload or {}).get("data") or {})
    refresh_token = str(data.pop("refreshToken", "") or "")
    access_token = str(data.get("accessToken") or "")
    if not refresh_token or not access_token:
        raise unauthorized("刷新令牌签发失败，请重新登录")
    actual_channel = _channel_from_access_token(access_token)
    if expected_channel is not None and actual_channel != _normalize_channel(expected_channel):
        # Login/refresh already created a durable refresh record. Burn it before rejecting a
        # cross-surface identity so an accidental student-on-staff (or staff-on-student) login
        # cannot overwrite or leave behind another PC surface's resumable browser session.
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


@router.post("/auth/browser-login", summary="浏览器账号密码登录（入口身份匹配 + 独立 HttpOnly refresh Cookie）")
def browser_login(body: auth_api.PasswordLoginRequest, response: Response):
    expected_channel = _channel_from_client_type(body.clientType)
    return _extract_refresh(auth_api.login(body), response, expected_channel=expected_channel)


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
    payload = auth_api.refresh(auth_api.RefreshRequest(refreshToken=refresh_token))
    return _extract_refresh(payload, response, expected_channel=channel)


@router.post("/auth/browser-switch-role", summary="浏览器切换身份并轮换对应入口的 HttpOnly refreshToken")
def browser_switch_role(
    body: SwitchRoleRequest,
    response: Response,
    user=Depends(get_current_user),
):
    payload = auth_api.switch_role(body, user)
    return _extract_refresh(payload, response)


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
    try:
        if refresh_token:
            refresh_claims = consume_refresh(refresh_token)
            if refresh_claims:
                refresh_user = str(refresh_claims.get("userId") or "")
                if refresh_user:
                    user_ids.add(refresh_user)

        raw = (authorization or "")[7:].strip() if (authorization or "").startswith("Bearer ") else (authorization or "").strip()
        if raw:
            try:
                access_claims = decode_token(raw)
            except AppException:
                access_claims = {}
            if access_claims:
                access_user = str(access_claims.get("userId") or "")
                if access_user:
                    user_ids.add(access_user)
                jti = str(access_claims.get("jti") or "")
                if jti:
                    block_jti(jti, float(access_claims.get("exp") or 0) or None)

        for user_id in user_ids:
            revoke_refresh_by_user(user_id)
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
