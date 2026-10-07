"""Native/mobile authentication for the standalone internship app.

Unlike browser PC auth, native mini-program clients receive a rotating refresh
token in JSON because they do not use browser HttpOnly cookies.  The authority
is still the standalone t_tenant/t_user/t_role/t_user_role database only.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Body, Depends, Header
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.api.v1.standalone_browser_auth import _resolve_account, _roles_for_user
from app.config import settings
from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException, unauthorized
from app.core.response import success
from app.core.security import _validate_db_subject, create_access_token, decode_token, get_current_user
from app.core.token_store import block_jti, consume_refresh, issue_refresh
from app.db.session import get_sessionmaker
from app.models import Tenant, User
from app.services import audit_log
from app.services.browser_auth_session_blocklist import auth_session_blocked, block_auth_session

router = APIRouter(prefix="/auth", tags=["Standalone mobile auth"])

_ALLOWED_CLIENTS = frozenset({"STUDENT_MINI", "TEACHER_MINI"})


class MobileLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tenantCode: str | None = Field(default=None, max_length=50)
    loginName: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)
    clientType: str = Field(default="STUDENT_MINI", max_length=40)

    @model_validator(mode="after")
    def validate_client(self):
        self.clientType = str(self.clientType or "").strip().upper()
        if self.clientType not in _ALLOWED_CLIENTS:
            raise ValueError("clientType 必须是 STUDENT_MINI 或 TEACHER_MINI")
        return self


class MobileRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    refreshToken: str = Field(min_length=20, max_length=1024)


class MobileLogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    refreshToken: str | None = Field(default=None, max_length=1024)


class MobileSwitchRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    roleCode: str = Field(min_length=2, max_length=50)
    refreshToken: str = Field(min_length=20, max_length=1024)


def _available_role_payload(roles: list[tuple[str, str]]) -> list[dict]:
    return [
        {"roleCode": str(code).upper(), "roleName": str(name or code),
         "contextId": f"role-{str(code).lower()}"}
        for code, name in roles
    ]


def _claims(*, tenant, user, role_code: str, role_name: str, client_type: str) -> dict:
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
        "authSessionId": secrets.token_urlsafe(24),
    }


def _public_payload(
    *, claims: dict, access_token: str, refresh_token: str,
    available_roles: list[tuple[str, str]] | None = None,
) -> dict:
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "tokenType": "Bearer",
        "expiresIn": int(settings.JWT_EXPIRES_IN),
        "user": {
            "userId": claims["userId"],
            "loginName": claims["loginName"],
            "realName": claims["realName"],
            "userType": claims["userType"],
            "studentNo": claims["loginName"] if str(claims["userType"]).upper() == "STUDENT" else None,
        },
        "currentRole": {
            "roleCode": claims["currentRoleCode"],
            "roleName": claims["currentRoleName"],
            "contextId": claims["activeContextId"],
        },
        "availableRoles": _available_role_payload(available_roles or [
            (claims["currentRoleCode"], claims["currentRoleName"])
        ]),
        "tenantId": claims["tenantId"],
        "tenantCode": claims["tenantCode"],
        "tenantName": claims["tenantName"],
        "mustChangePassword": claims["mustChangePassword"],
        "credentialVersion": claims["credentialVersion"],
    }


@router.post("/login", summary="Standalone 学生/教师移动端账号密码登录")
def mobile_login(body: MobileLoginRequest):
    db = get_sessionmaker()()
    try:
        tenant, user, role_code, role_name = _resolve_account(db, body)
        roles = _roles_for_user(db, tenant_id=int(tenant.id), user=user)
        client_type = body.clientType
        is_student = role_code == "STUDENT" or str(user.user_type or "").upper() == "STUDENT"
        if client_type == "STUDENT_MINI" and not is_student:
            raise AppException("NO_PERMISSION", "请使用学生账号登录学生端", http_status=403)
        if client_type == "TEACHER_MINI" and is_student:
            raise AppException("NO_PERMISSION", "学生账号不能登录教师端", http_status=403)

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
            client_type=client_type,
        )
        set_current_user(dict(claims))
        access_token = create_access_token(claims)
        refresh_token = issue_refresh(claims)
        audit_log.record(
            "MOBILE_PASSWORD_LOGIN",
            f"user:{user.id}",
            detail={
                "tenantId": int(tenant.id),
                "clientType": client_type,
                "roleCode": role_code,
            },
        )
        return success(
            _public_payload(
                claims=claims,
                access_token=access_token,
                refresh_token=refresh_token,
                available_roles=roles,
            ),
            message="登录成功",
        )
    finally:
        db.close()




@router.post("/switch-role", summary="Standalone 教师移动端同账号切换已授权身份")
def mobile_switch_role(body: MobileSwitchRoleRequest, user=Depends(get_current_user)):
    client_type = str((user or {}).get("clientType") or "").strip().upper()
    if client_type != "TEACHER_MINI":
        raise AppException("NO_PERMISSION", "仅教师移动端支持工作身份切换", http_status=403)
    raw_user_id = str((user or {}).get("userId") or "")
    raw_tenant_id = str((user or {}).get("tenantId") or "")
    if not raw_user_id.startswith("db-") or not raw_user_id[3:].isdigit() or not raw_tenant_id.isdigit():
        raise unauthorized("当前账号身份无效，请重新登录")

    db = get_sessionmaker()()
    try:
        tenant = db.scalar(select(Tenant).where(
            Tenant.id == int(raw_tenant_id), Tenant.is_deleted.is_(False), Tenant.status == "ACTIVE"))
        account = db.scalar(select(User).where(
            User.id == int(raw_user_id[3:]), User.tenant_id == int(raw_tenant_id),
            User.is_deleted.is_(False), User.status == "ACTIVE"))
        if not tenant or not account:
            raise unauthorized("账号或学校已停用，请重新登录")
        roles = _roles_for_user(db, tenant_id=int(tenant.id), user=account)
        target_code = str(body.roleCode or "").strip().upper()
        target = next(((code, name) for code, name in roles if str(code).upper() == target_code), None)
        if not target or target_code == "STUDENT":
            raise AppException("NO_PERMISSION", "当前账号未分配该教师工作身份", http_status=403)

        refresh_claims = consume_refresh(body.refreshToken, expected_claims=user)
        if not refresh_claims:
            raise unauthorized("当前会话已变化，请刷新页面后重试身份切换")
        claims = _claims(
            tenant=tenant, user=account, role_code=str(target[0]),
            role_name=str(target[1]), client_type=client_type)
        access_token = create_access_token(claims)
        refresh_token = issue_refresh(claims)
        audit_log.record(
            "MOBILE_ROLE_SWITCH", f"user:{account.id}",
            detail={"tenantId": int(tenant.id),
                    "fromRole": str((user or {}).get("currentRoleCode") or ""),
                    "toRole": str(target[0]), "clientType": client_type})
        return success(_public_payload(
            claims=claims, access_token=access_token, refresh_token=refresh_token,
            available_roles=roles), message="身份切换成功")
    finally:
        db.close()


@router.post("/refresh", summary="Standalone 移动端刷新令牌")
def mobile_refresh(body: MobileRefreshRequest):
    claims = consume_refresh(body.refreshToken)
    if not claims:
        raise unauthorized("refreshToken 无效或已使用，请重新登录")
    client_type = str(claims.get("clientType") or "").upper()
    if client_type not in _ALLOWED_CLIENTS:
        raise unauthorized("移动端会话类型无效，请重新登录")
    if auth_session_blocked(claims.get("authSessionId")):
        raise unauthorized("当前会话已退出，请重新登录")

    tenant_id = claims.get("tenantId") or claims.get("tenant_id")
    if not tenant_id:
        raise unauthorized("令牌缺少学校上下文")
    set_tenant({
        "tenantId": str(tenant_id),
        "tenantCode": str(claims.get("tenantCode") or ""),
        "schoolName": str(claims.get("tenantName") or ""),
    })
    set_current_user(dict(claims))
    validated = _validate_db_subject(dict(claims), "/api/v1/auth/refresh")
    access_token = create_access_token(validated)
    refresh_token = issue_refresh(validated)
    return success({
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "tokenType": "Bearer",
        "expiresIn": int(settings.JWT_EXPIRES_IN),
    }, message="已刷新")


@router.post("/logout", summary="Standalone 移动端登出当前会话")
def mobile_logout(
    body: MobileLogoutRequest | None = Body(default=None),
    authorization: str | None = Header(default=None),
):
    session_id = ""
    if body and body.refreshToken:
        claims = consume_refresh(body.refreshToken)
        if claims:
            session_id = str(claims.get("authSessionId") or "")
    raw = str(authorization or "").strip()
    if raw.lower().startswith("bearer "):
        raw = raw.split(None, 1)[1].strip()
        try:
            claims = decode_token(raw)
            session_id = session_id or str(claims.get("authSessionId") or "")
            jti = str(claims.get("jti") or "")
            if jti:
                block_jti(jti, float(claims.get("exp") or 0) or None)
        except AppException:
            pass
    if session_id:
        block_auth_session(session_id)
    return success({"invalidated": True}, message="已退出登录")
