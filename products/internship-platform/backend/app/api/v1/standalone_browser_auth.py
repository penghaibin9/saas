"""Standalone browser authentication for school staff and student PC surfaces.

This module is intentionally self-contained inside the extracted internship product.
It authenticates only local t_tenant/t_user/t_role/t_user_role facts, issues access
tokens in memory and rotates one HttpOnly refresh cookie per browser tab.

It does not import the parent SaaS auth service or platform control-plane identity.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.config import settings
from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException, unauthorized
from app.core.response import success
from app.core.security import create_access_token, verify_password
from app.core.token_store import (
    REFRESH_TTL,
    consume_refresh_if_matches,
    issue_refresh,
)
from app.db.session import get_sessionmaker
from app.models import Role, Tenant, User, UserRole
from app.services.browser_auth_session_blocklist import auth_session_blocked, block_auth_session, revoke_logout_credentials
from app.services.system_authorization import audit

router = APIRouter(prefix="/auth", tags=["Standalone browser auth"])

_COOKIE_PATH = "/api/v1/auth"
_COOKIE_PREFIX = {
    "staff": "ix_staff_refresh_v1_",
    "student": "ix_student_refresh_v1_",
}


class BrowserLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tenantCode: str | None = Field(default=None, max_length=50)
    loginName: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)
    clientType: str = Field(default="PC", max_length=40)


def _browser_session_id(value: str | None) -> str:
    session_id = str(value or "").strip()
    if not session_id or len(session_id) > 256:
        raise unauthorized("浏览器标签页会话无效，请重新登录")
    return session_id


def _session_hash(session_id: str) -> str:
    return hashlib.sha256(_browser_session_id(session_id).encode("utf-8")).hexdigest()


def _channel_from_client_type(client_type: str | None) -> str:
    client = str(client_type or "").strip().upper()
    return "student" if client in {"STUDENT_PC", "STUDENT_MINI"} else "staff"


def _cookie_name(channel: str, session_id: str) -> str:
    if channel not in _COOKIE_PREFIX:
        raise unauthorized("浏览器会话通道无效，请重新登录")
    return f"{_COOKIE_PREFIX[channel]}{_session_hash(session_id)[:24]}"


def _set_refresh_cookie(response: Response, token: str, channel: str, session_id: str) -> None:
    response.set_cookie(
        key=_cookie_name(channel, session_id),
        value=token,
        max_age=int(REFRESH_TTL),
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
        path=_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response, channel: str, session_id: str) -> None:
    response.delete_cookie(
        key=_cookie_name(channel, session_id),
        path=_COOKIE_PATH,
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
    )


def _roles_for_user(db, *, tenant_id: int, user: User) -> list[tuple[str, str]]:
    rows = db.execute(
        select(Role.role_code, Role.role_name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.tenant_id == tenant_id,
            UserRole.user_id == user.id,
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
            Role.tenant_id == tenant_id,
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
        )
        .order_by(UserRole.id)
    ).all()
    if rows:
        return [(str(row[0]), str(row[1])) for row in rows]

    raise AppException("NO_PERMISSION", "账号未分配岗位实习可用角色", http_status=403)


def _role_for_user(db, *, tenant_id: int, user: User) -> tuple[str, str]:
    return _roles_for_user(db, tenant_id=tenant_id, user=user)[0]


def _resolve_account(db, body: BrowserLoginRequest) -> tuple[Tenant, User, str, str]:
    try:
        return _authenticate_account(db, body)
    except AppException as exc:
        # An unauthenticated attempt is never attributed to the account owner.
        query = select(Tenant.id, User.id).outerjoin(User, (User.tenant_id == Tenant.id) &
            (User.login_name == body.loginName.strip()) & User.is_deleted.is_(False))
        code = str(body.tenantCode or '').strip()
        query = query.where(Tenant.tenant_code == code) if code else query.where(User.id.is_not(None))
        matches = db.execute(query.where(Tenant.is_deleted.is_(False)).limit(2)).all()
        if len(matches) == 1:
            tenant_id, account_id = matches[0]
            audit(db, {'tenantId': tenant_id, 'realName': '未认证访问'}, 'LOGIN_DENIED', 'account',
                  account_id or '', {'reason': exc.message}, result='DENIED')
            db.commit()
        raise


def _authenticate_account(db, body: BrowserLoginRequest) -> tuple[Tenant, User, str, str]:
    login_name = body.loginName.strip()
    tenant_code = str(body.tenantCode or "").strip()

    stmt = (
        select(Tenant, User)
        .join(User, User.tenant_id == Tenant.id)
        .where(
            Tenant.is_deleted.is_(False),
            Tenant.status == "ACTIVE",
            User.login_name == login_name,
            User.is_deleted.is_(False),
            User.status == "ACTIVE",
        )
    )
    if tenant_code:
        stmt = stmt.where(Tenant.tenant_code == tenant_code)

    rows = db.execute(stmt.limit(3)).all()
    if not rows:
        raise unauthorized("账号、学校编码或密码不正确")
    if len(rows) != 1:
        raise AppException("VALIDATION_ERROR", "该账号存在于多所学校，请填写学校编码", http_status=422)

    tenant, user = rows[0]
    if not verify_password(body.password, user.password_hash):
        raise unauthorized("账号、学校编码或密码不正确")
    if user.expires_at and user.expires_at <= datetime.utcnow():
        raise unauthorized("账号有效期已结束，请联系学校管理员")

    role_code, role_name = _role_for_user(db, tenant_id=int(tenant.id), user=user)
    channel = _channel_from_client_type(body.clientType)
    if channel == "student" and role_code != "STUDENT" and str(user.user_type or "").upper() != "STUDENT":
        raise AppException("NO_PERMISSION", "请使用学生账号登录学生端", http_status=403)
    if channel == "staff" and (role_code == "STUDENT" or str(user.user_type or "").upper() == "STUDENT"):
        raise AppException("NO_PERMISSION", "学生账号请使用学生端登录", http_status=403)
    return tenant, user, role_code, role_name


def _claims(*, tenant: Tenant, user: User, role_code: str, role_name: str, channel: str, session_id: str) -> dict:
    auth_session_id = secrets.token_urlsafe(24)
    client_type = "STUDENT_PC" if channel == "student" else "PC"
    return {
        "userId": f"db-{user.id}",
        "loginName": user.login_name,
        "realName": user.real_name,
        "userType": user.user_type,
        "tenantId": str(tenant.id),
        "tenantCode": tenant.tenant_code,
        "tenantName": tenant.school_name,
        "currentRoleCode": role_code,
        "currentRoleName": role_name,
        "activeContextId": f"role-{role_code.lower()}",
        "clientType": client_type,
        "credentialVersion": int(user.credential_version or 0),
        "mustChangePassword": bool(user.must_change_password),
        "authSessionId": auth_session_id,
        "browserChannel": channel,
        "browserSessionIdHash": _session_hash(session_id),
    }


def _public_payload(*, access_token: str, tenant: Tenant, user: User, role_code: str, role_name: str) -> dict:
    return {
        "accessToken": access_token,
        "tokenType": "Bearer",
        "expiresIn": int(settings.JWT_EXPIRES_IN),
        "user": {
            "userId": f"db-{user.id}",
            "loginName": user.login_name,
            "realName": user.real_name,
            "userType": user.user_type,
            "studentNo": user.login_name if str(user.user_type or "").upper() == "STUDENT" else None,
        },
        "currentRole": {"roleCode": role_code, "roleName": role_name},
        "tenantId": str(tenant.id),
        "tenantCode": tenant.tenant_code,
        "tenantName": tenant.school_name,
        "mustChangePassword": bool(user.must_change_password),
        "credentialVersion": int(user.credential_version or 0),
    }


@router.post("/browser-login", summary="Standalone PC 账号密码登录")
def browser_login(
    body: BrowserLoginRequest,
    response: Response,
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    tab_id = _browser_session_id(browser_session_id)
    db = get_sessionmaker()()
    try:
        tenant, user, role_code, role_name = _resolve_account(db, body)
        channel = _channel_from_client_type(body.clientType)
        set_tenant({
            "tenantId": str(tenant.id),
            "tenantCode": tenant.tenant_code,
            "schoolName": tenant.school_name,
        })
        claims = _claims(
            tenant=tenant,
            user=user,
            role_code=role_code,
            role_name=role_name,
            channel=channel,
            session_id=tab_id,
        )
        set_current_user(dict(claims))
        access_token = create_access_token(claims)
        refresh_token = issue_refresh(claims)
        _set_refresh_cookie(response, refresh_token, channel, tab_id)
        user.last_login_at = datetime.utcnow()
        audit(db, claims, 'LOGIN', 'account', user.id, {'reason': '账号密码登录'})
        db.commit()
        return success(
            _public_payload(
                access_token=access_token,
                tenant=tenant,
                user=user,
                role_code=role_code,
                role_name=role_name,
            ),
            message="登录成功",
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/browser-refresh", summary="Standalone PC 刷新当前标签页会话")
def browser_refresh(
    request: Request,
    response: Response,
    browser_session: str | None = Header(default=None, alias="X-Browser-Session"),
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    channel = str(browser_session or "").strip().lower()
    if channel not in _COOKIE_PREFIX:
        raise unauthorized("浏览器会话通道无效，请重新登录")
    tab_id = _browser_session_id(browser_session_id)
    refresh_token = request.cookies.get(_cookie_name(channel, tab_id))
    if not refresh_token:
        raise unauthorized("浏览器刷新会话不存在，请重新登录")

    claims = consume_refresh_if_matches(
        refresh_token,
        expected_browser_channel=channel,
        expected_browser_session_hash=_session_hash(tab_id),
    )
    if not claims:
        _clear_refresh_cookie(response, channel, tab_id)
        raise unauthorized("浏览器刷新会话无效，请重新登录")
    if not claims.get("authSessionId") or auth_session_blocked(claims.get("authSessionId")):
        _clear_refresh_cookie(response, channel, tab_id)
        raise unauthorized("浏览器会话已退出，请重新登录")

    # Reuse the request-time DB subject guard to fail closed after password reset/account disable.
    from app.core.security import _validate_db_subject

    claims = _validate_db_subject(dict(claims), "/api/v1/auth/browser-refresh")
    access_token = create_access_token(claims)
    new_refresh = issue_refresh(claims)
    _set_refresh_cookie(response, new_refresh, channel, tab_id)
    return success({
        "accessToken": access_token,
        "tokenType": "Bearer",
        "expiresIn": int(settings.JWT_EXPIRES_IN),
    }, message="已刷新")


@router.post("/browser-logout", summary="Standalone PC 登出当前标签页")
def browser_logout(
    request: Request,
    response: Response,
    browser_session: str | None = Header(default=None, alias="X-Browser-Session"),
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
    authorization: str | None = Header(default=None),
):
    channel = str(browser_session or "").strip().lower()
    if channel not in _COOKIE_PREFIX:
        raise unauthorized("浏览器会话通道无效，请重新登录")
    tab_id = _browser_session_id(browser_session_id)
    refresh_token = request.cookies.get(_cookie_name(channel, tab_id))
    refresh_claims = None
    if refresh_token:
        refresh_claims = consume_refresh_if_matches(
            refresh_token,
            expected_browser_channel=channel,
            expected_browser_session_hash=_session_hash(tab_id),
        )
    invalidated = revoke_logout_credentials(authorization, refresh_claims)
    _clear_refresh_cookie(response, channel, tab_id)
    return success({"invalidated": invalidated}, message="已登出" if invalidated else "未确认服务端会话撤销，请重新登录")


class BrowserSwitchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    contextId: str = Field(min_length=6, max_length=100)
    clientType: str = Field(default='PC', pattern='^PC$')


from app.core.security import get_current_user


@router.post('/browser-switch-role', summary='切换当前浏览器工作身份')
def browser_switch_role(body: BrowserSwitchRequest, request: Request, response: Response,
                        browser_session_id: str | None = Header(default=None, alias='X-Browser-Session-Id'),
                        user=Depends(get_current_user)):
    from app.services.system_authorization import active_roles, audit
    tab_id = _browser_session_id(browser_session_id)
    if user.get('browserChannel') != 'staff' or user.get('browserSessionIdHash') != _session_hash(tab_id):
        raise unauthorized('当前标签页与登录会话不一致，请重新登录')
    with get_sessionmaker()() as db:
        account = db.get(User, int(str(user['userId']).removeprefix('db-')))
        tenant = db.get(Tenant, int(user['tenantId']))
        target = next((r for r in active_roles(db, tenant.id, account.id)
                       if f'role-{r.role_code.lower()}' == body.contextId and r.role_code != 'STUDENT'), None)
        if not target:
            raise AppException('NO_PERMISSION', '当前账号没有这个有效工作身份', http_status=403)
        refresh = request.cookies.get(_cookie_name('staff', tab_id))
        previous = consume_refresh_if_matches(refresh or '', expected_browser_channel='staff',
                                               expected_browser_session_hash=_session_hash(tab_id))
        if not previous or previous.get('authSessionId') != user.get('authSessionId'):
            raise unauthorized('当前会话已变化，请重新登录')
        block_auth_session(str(user.get('authSessionId') or ''))
        claims = _claims(tenant=tenant, user=account, role_code=target.role_code, role_name=target.role_name,
                         channel='staff', session_id=tab_id)
        audit(db, user, 'ROLE_SWITCH', 'account', account.id, {'fromRole': user['currentRoleCode'], 'toRole': target.role_code})
        db.commit()
        token = create_access_token(claims)
        _set_refresh_cookie(response, issue_refresh(claims), 'staff', tab_id)
        return success(_public_payload(access_token=token, tenant=tenant, user=account,
                                       role_code=target.role_code, role_name=target.role_name), message='身份已切换')
