"""Enterprise portal browser-only auth transport.

The enterprise PC keeps access tokens in JavaScript memory only. Refresh credentials are rotated
through per-tab HttpOnly cookies and are cryptographically bound in the persisted refresh claims to
the exact tab id hash. An F5 can restore the session without browser-readable bearer persistence.
Native/legacy JSON refresh endpoints remain unchanged for existing non-browser consumers.
"""
from __future__ import annotations

import hashlib
import secrets

from fastapi import APIRouter, Header, Request, Response

from app.core.config import settings
from app.core.exceptions import AppException, unauthorized
from app.core.response import success
from app.core.security import create_access_token, decode_token
from app.core.token_store import (
    REFRESH_TTL,
    block_jti,
    consume_refresh,
    consume_refresh_if_matches,
    issue_refresh,
)
from app.modules.internship.schemas.internship_recruitment_campaign import (
    EnterpriseInviteAccept,
    EnterpriseLogin,
)
from app.modules.internship.services import internship_enterprise_auth_service as auth_svc
from app.services import audit_log
from app.services.browser_auth_session_blocklist import auth_session_blocked, block_auth_session

# Keep the complete /auth/... path on each decorator. The internship route-permission audit is
# intentionally static/source-based and must be able to prove that every public endpoint lives
# under the frozen auth namespace without reconstructing nested APIRouter prefixes.
router = APIRouter(tags=["岗位实习-企业协同端-浏览器认证"])

_COOKIE_PATH = "/api/v1/internship/enterprise-portal/auth"
_COOKIE_PREFIX = "gx_enterprise_refresh_v1_"
_BROWSER_CHANNEL = "enterprise"


def _require_tab_id(value: str | None) -> str:
    tab_id = str(value or "").strip()
    if not tab_id or len(tab_id) > 256:
        raise unauthorized("企业浏览器标签页会话无效，请重新登录")
    return tab_id


def _tab_hash(tab_id: str) -> str:
    return hashlib.sha256(_require_tab_id(tab_id).encode("utf-8")).hexdigest()


def _cookie_name(tab_id: str) -> str:
    return f"{_COOKIE_PREFIX}{_tab_hash(tab_id)[:24]}"


def _set_refresh_cookie(response: Response, refresh_token: str, tab_id: str) -> None:
    response.set_cookie(
        key=_cookie_name(tab_id),
        value=refresh_token,
        max_age=int(REFRESH_TTL),
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
        path=_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response, tab_id: str) -> None:
    response.delete_cookie(
        key=_cookie_name(tab_id),
        path=_COOKIE_PATH,
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
    )


def _sessionize_result(result: dict, tab_id: str) -> tuple[dict, str]:
    """Replace the service-issued pair with an exact-tab-bound pair before exposing it."""
    data = dict(result or {})
    refresh_token = str(data.pop("refreshToken", "") or "")
    access_token = str(data.get("accessToken", "") or "")
    if not refresh_token or not access_token:
        raise unauthorized("企业浏览器会话签发失败，请重新登录")
    claims = consume_refresh(refresh_token)
    if not claims:
        raise unauthorized("企业浏览器刷新令牌签发失败，请重新登录")
    claims["authSessionId"] = str(claims.get("authSessionId") or secrets.token_urlsafe(24))
    claims["browserChannel"] = _BROWSER_CHANNEL
    claims["browserSessionIdHash"] = _tab_hash(tab_id)
    data["accessToken"] = create_access_token(dict(claims))
    bound_refresh = issue_refresh(dict(claims))
    return data, bound_refresh


def _browser_result(result: dict, response: Response, tab_id: str) -> dict:
    data, refresh_token = _sessionize_result(result, tab_id)
    _set_refresh_cookie(response, refresh_token, tab_id)
    return data


def _rotate_refresh(refresh_token: str, tab_id: str) -> tuple[dict, str]:
    claims = consume_refresh_if_matches(
        refresh_token,
        expected_browser_channel=_BROWSER_CHANNEL,
        expected_browser_session_hash=_tab_hash(tab_id),
    )
    if not claims:
        raise unauthorized("企业浏览器刷新会话无效，请重新登录")
    auth_session_id = str(claims.get("authSessionId") or "").strip()
    if not auth_session_id or auth_session_blocked(auth_session_id):
        raise unauthorized("企业浏览器会话已登出失效，请重新登录")
    # Revalidate live tenant/user/member/company admission and permissionVersion before rotation.
    auth_svc.validate_enterprise_claims(claims)
    claims["authSessionId"] = auth_session_id
    claims["browserChannel"] = _BROWSER_CHANNEL
    claims["browserSessionIdHash"] = _tab_hash(tab_id)
    return {
        "accessToken": create_access_token(dict(claims)),
        "tokenType": "Bearer",
        "expiresIn": settings.JWT_EXPIRES_IN,
    }, issue_refresh(dict(claims))


@router.post("/auth/browser-login", openapi_extra={"x-internship-auth": "public"})
def browser_login(
    body: EnterpriseLogin,
    response: Response,
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    tab_id = _require_tab_id(browser_session_id)
    result = auth_svc.login(
        tenant_code=body.tenantCode,
        login_name=body.loginName,
        password=body.password,
        member_id=body.memberId,
    )
    audit_log.record(
        "ENTERPRISE_LOGIN",
        f"enterprise-member:{result['context']['memberId']}",
        detail={"companyId": result["context"]["companyId"], "transport": "BROWSER_COOKIE"},
        tenant_id=int(result["context"]["tenantId"]),
    )
    return success(_browser_result(result, response, tab_id))


@router.post("/auth/browser-invite/accept", openapi_extra={"x-internship-auth": "public"})
def browser_accept_invite(
    body: EnterpriseInviteAccept,
    response: Response,
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    tab_id = _require_tab_id(browser_session_id)
    result = auth_svc.accept_invite(
        tenant_code=body.tenantCode,
        token=body.token,
        phone=body.phone,
        password=body.password,
    )
    audit_log.record(
        "ENTERPRISE_INVITE_ACCEPT",
        f"enterprise-member:{result['context']['memberId']}",
        detail={"companyId": result["context"]["companyId"], "transport": "BROWSER_COOKIE"},
        tenant_id=int(result["context"]["tenantId"]),
    )
    return success(_browser_result(result, response, tab_id), message="企业邀请已接受")


@router.post("/auth/browser-refresh", openapi_extra={"x-internship-auth": "public"})
def browser_refresh(
    request: Request,
    response: Response,
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    tab_id = _require_tab_id(browser_session_id)
    refresh_token = request.cookies.get(_cookie_name(tab_id))
    if not refresh_token:
        raise unauthorized("企业浏览器刷新会话不存在，请重新登录")
    try:
        data, new_refresh = _rotate_refresh(refresh_token, tab_id)
    except AppException:
        _clear_refresh_cookie(response, tab_id)
        raise
    _set_refresh_cookie(response, new_refresh, tab_id)
    return success(data, message="已刷新")


@router.post("/auth/browser-logout", openapi_extra={"x-internship-auth": "public"})
def browser_logout(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    tab_id = _require_tab_id(browser_session_id)
    refresh_token = request.cookies.get(_cookie_name(tab_id))
    _clear_refresh_cookie(response, tab_id)
    refresh_claims = None
    if refresh_token:
        try:
            refresh_claims = consume_refresh_if_matches(
                refresh_token,
                expected_browser_channel=_BROWSER_CHANNEL,
                expected_browser_session_hash=_tab_hash(tab_id),
            )
        except Exception:  # noqa: BLE001 - cookie deletion still succeeds
            pass
    raw = (authorization or "").strip()
    raw = raw[7:].strip() if raw.startswith("Bearer ") else raw
    access_claims = None
    if raw:
        try:
            access_claims = decode_token(raw)
            jti = str(access_claims.get("jti") or "")
            if jti:
                block_jti(jti, float(access_claims.get("exp") or 0) or None)
        except Exception:  # noqa: BLE001 - an expired/invalid access token must not prevent cookie deletion
            pass
    # Block the entire browser auth-session family, not only the currently presented JTI. This
    # invalidates older access tokens issued before a refresh as well as any surviving refresh row.
    auth_session_id = str(
        (access_claims or {}).get("authSessionId")
        or (refresh_claims or {}).get("authSessionId")
        or ""
    ).strip()
    if auth_session_id:
        block_auth_session(auth_session_id)
    return success({"invalidated": True}, message="已登出")
