"""Browser-only auth transport.

PC surfaces keep access tokens in memory only and rotate refresh tokens through an HttpOnly
cookie. Miniapp/native clients continue using the existing JSON refresh-token transport because
those runtimes do not share the browser cookie threat model.
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

_COOKIE_NAME = "gx_refresh_v1"
_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        max_age=int(REFRESH_TTL),
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
        path=_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_COOKIE_NAME,
        path=_COOKIE_PATH,
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
    )


def _extract_refresh(payload: dict, response: Response) -> dict:
    """Move refreshToken from JSON into HttpOnly cookie; accessToken remains response data."""
    data = dict((payload or {}).get("data") or {})
    refresh_token = str(data.pop("refreshToken", "") or "")
    if not refresh_token:
        raise unauthorized("刷新令牌签发失败，请重新登录")
    _set_refresh_cookie(response, refresh_token)
    out = dict(payload)
    out["data"] = data
    return out


@router.post("/auth/browser-login", summary="浏览器账号密码登录（refreshToken 仅 HttpOnly Cookie）")
def browser_login(body: auth_api.PasswordLoginRequest, response: Response):
    return _extract_refresh(auth_api.login(body), response)


@router.post("/auth/browser-refresh", summary="浏览器刷新会话（读取并轮换 HttpOnly Cookie）")
def browser_refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_COOKIE_NAME),
):
    if not refresh_token:
        raise unauthorized("浏览器刷新会话不存在，请重新登录")
    payload = auth_api.refresh(auth_api.RefreshRequest(refreshToken=refresh_token))
    return _extract_refresh(payload, response)


@router.post("/auth/browser-switch-role", summary="浏览器切换身份并轮换 HttpOnly refreshToken")
def browser_switch_role(
    body: SwitchRoleRequest,
    response: Response,
    user=Depends(get_current_user),
):
    payload = auth_api.switch_role(body, user)
    data = dict((payload or {}).get("data") or {})
    refresh_token = str(data.pop("refreshToken", "") or "")
    if refresh_token:
        _set_refresh_cookie(response, refresh_token)
    out = dict(payload)
    out["data"] = data
    return out


@router.post("/auth/browser-logout", summary="浏览器登出并清除 HttpOnly refreshToken")
def browser_logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_COOKIE_NAME),
    authorization: str | None = Header(default=None),
):
    """Terminate a browser session even when its in-memory access token has expired.

    The refresh cookie is the durable browser session. Requiring a live access token here makes
    logout ineffective precisely after access expiry: JS clears its memory, but the surviving
    HttpOnly cookie silently logs the user back in on reload. Therefore logout authenticates the
    durable session by consuming the cookie itself, while a still-valid bearer token is also
    blacklisted when available.

    Store failures stay fail-closed (HTTP error), but the browser cookie is always expired in the
    response so a transient backend failure cannot leave a resumable session on a shared PC.
    """
    _clear_refresh_cookie(response)
    user_id = ""
    try:
        if refresh_token:
            refresh_claims = consume_refresh(refresh_token)
            if refresh_claims:
                user_id = str(refresh_claims.get("userId") or "")

        raw = (authorization or "")[7:].strip() if (authorization or "").startswith("Bearer ") else (authorization or "").strip()
        if raw:
            try:
                access_claims = decode_token(raw)
            except AppException:
                # Expired/invalid access must never prevent clearing the durable browser session.
                access_claims = {}
            if access_claims:
                user_id = user_id or str(access_claims.get("userId") or "")
                jti = str(access_claims.get("jti") or "")
                if jti:
                    block_jti(jti, float(access_claims.get("exp") or 0) or None)

        if user_id:
            revoke_refresh_by_user(user_id)
    except AppException as exc:
        # Preserve the Set-Cookie deletion while exposing the real fail-closed store error.
        response.status_code = int(exc.http_status)
        return fail(exc.code, exc.message, exc.details)

    audit.record(
        "登出",
        method="POST",
        path="/api/v1/auth/browser-logout",
        status_code=200,
        target_type="auth",
        target_id=user_id or "-",
    )
    return success({"invalidated": True}, message="已登出")
